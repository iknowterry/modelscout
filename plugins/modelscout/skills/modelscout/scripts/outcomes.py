#!/usr/bin/env python3
"""ModelScout outcomes: how did each routed subagent end?

Append-only JSONL in ~/.claude/modelscout-outcomes.jsonl. Two kinds of line:
  outcome  {"id","ts","host","tier","model","status"[,"why"]}
  update   {"ts","ref","status"[,"model"][,"why"]}   folds into the outcome `ref`
  marker   {"ts","reset":true}   read() ignores every line written before the latest one
Only ids, timestamps, host, tier, model, status and a coarse reason bucket are
stored: never goal text, prompts, output, error text or transcript paths.

States:
  pending  an async subagent was launched and has not finished yet
  ok       the subagent finished (says nothing about quality)
  weak     a quality verdict: the user said `modelscout: weak`, or the main
           model ran `outcomes.py weak` after redoing the work. This is the ONLY
           state that counts against a model (see weak_rate).
  error    infrastructure or interruption (usage limit, model unavailable,
           permission denied, API error, user interrupt). Neutral for learning.
Allowed updates: pending -> ok | error, ok -> weak. Anything else is ignored, so
a repeated update is a no-op.

Older lines (status "ok"/"fail", updates {"ref","verdict":"fail"}) still read:
a base "fail" is an unverified failure and reads as error; a "fail" verdict
reads as weak.

Usage:
  outcomes.py weak       # mark the latest finished result as weak
  outcomes.py forget     # start learning fresh (history stays on disk)
  outcomes.py summary    # outcomes per tier and model
"""
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

OUTCOMES = Path.home() / ".claude" / "modelscout-outcomes.jsonl"
TAG = re.compile(r"^\s*(?:⚡\s*)?modelscout\s*:\s*(t[1-4])\b", re.I)
MARK = re.compile(r"^\s*(?:⚡\s*)?modelscout\b", re.I)
FAIL_STATUSES = {"failed", "error", "interrupted", "timeout", "timed_out", "cancelled"}
STATES = ("pending", "ok", "weak", "error")
TIERS = ("T1", "T2", "T3", "T4")
PENDING_TTL = 86400  # summary ignores pending records older than a day
_NEXT = {"pending": ("ok", "error"), "ok": ("weak",)}
_REASONS = (  # first match wins; "limit" before generic API-error text
    ("interrupt", re.compile(r"interrupt|aborted|cancel", re.I)),
    ("limit", re.compile(r"rate.?limit|usage limit|session limit|quota|\b429\b|hit your .{0,20}limit", re.I)),
    ("unavailable", re.compile(r"unavailable|overload|server.?error|connection|timed? ?out|timeout|\b5\d\d\b", re.I)),
    ("denied", re.compile(r"denied|permission|authenticat|unauthori|forbidden|\b40[13]\b", re.I)),
)


def tier_from(text):
    """"ModelScout: T1 · rename …" → "T1"; None when untagged."""
    m = TAG.match(text or "")
    return m.group(1).upper() if m else None


def is_routed(text):
    return bool(MARK.match(text or ""))


def reason(*texts):
    """Coarse bucket for an error: limit / unavailable / denied / interrupt /
    other. Only the bucket is ever stored, never the text."""
    s = " ".join(str(t) for t in texts if t)[:2000]
    for name, rx in _REASONS:
        if rx.search(s):
            return name
    return "other"


def _bucket(why):
    w = re.sub(r"[^a-z_]", "", str(why or "").lower())[:20]
    return w


def _append(rec):
    """One os.write on an O_APPEND descriptor, so concurrent writers never
    interleave lines. Never raises."""
    try:
        line = (json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        if len(line) > 2048:
            return False
        OUTCOMES.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(OUTCOMES), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        return True
    except Exception:  # noqa: BLE001 - recording must never break a turn
        return False


def record(host, tier, model, status, why="", id=None):  # noqa: A002
    """Record one routed subagent; status "ok", "error" or "pending" (legacy
    "fail" → "error"). Returns the outcome id, or None if nothing was written."""
    status = status if status in ("ok", "pending") else "error"
    rid = str(id)[:64] if id else secrets.token_hex(4)
    rec = {"id": rid, "ts": round(time.time()), "host": str(host or "")[:16],
           "tier": tier if tier in TIERS else None, "model": (str(model)[:80] if model else None),
           "status": status}
    if status == "error":
        rec["why"] = _bucket(why) or "other"
    return rid if _append(rec) else None


def resolve(ref, status, model=None, why=""):
    """Finish a pending outcome as "ok" or "error". No-op (False) unless `ref`
    is still pending."""
    cur = find(ref)
    if not cur or cur["status"] != "pending" or status not in ("ok", "error"):
        return False
    upd = {"ts": round(time.time()), "ref": cur["id"], "status": status}
    if model:
        upd["model"] = str(model)[:80]
    if status == "error":
        upd["why"] = _bucket(why) or "other"
    return _append(upd)


def read():
    """Outcomes oldest first (by launch/record line), updates folded in. Each
    row also carries `done`: the time it finished (None while pending)."""
    out, by_id = [], {}
    try:
        lines = OUTCOMES.read_text().splitlines()
    except OSError:
        return []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        if r.get("reset") is True:  # forget(): learning starts fresh after the latest marker
            out.clear()
            by_id.clear()
            continue
        if r.get("ref") is not None:
            cur = by_id.get(r.get("ref"))
            if cur is None:
                continue
            new = r.get("status")
            if r.get("verdict") == "fail":  # legacy weak verdict
                new = "weak"
            if new not in _NEXT.get(cur["status"], ()):
                continue
            cur["status"] = new
            if new != "weak":
                cur["done"] = r.get("ts") or cur.get("done")
            if r.get("model") and new != "weak":
                cur["model"] = r["model"]
            if new == "error":
                cur["why"] = r.get("why") or "other"
            elif new == "weak":
                cur["why"] = "weak"
            continue
        rid, status = r.get("id"), r.get("status")
        if not rid or rid in by_id:
            continue
        if status == "fail":  # legacy unverified failure: neutral
            status = "error"
        if status not in ("ok", "pending", "error"):
            continue
        row = {"id": rid, "ts": r.get("ts") or 0, "host": r.get("host"), "tier": r.get("tier"),
               "model": r.get("model"), "status": status,
               "why": (r.get("why") or "other") if status == "error" else "",
               "done": None if status == "pending" else (r.get("ts") or 0)}
        by_id[rid] = row
        out.append(row)
    return out


def find(ref):
    for r in read():
        if r["id"] == ref:
            return r
    return None


def _finished(rows):
    """ok + weak rows, ordered by finish time (ties keep file order)."""
    fin = [(r.get("done") or 0, i, r) for i, r in enumerate(rows) if r["status"] in ("ok", "weak")]
    return [r for _, _, r in sorted(fin, key=lambda t: (t[0], t[1]))]


def mark_last_weak(why="weak"):
    """Mark the most recently FINISHED result as weak.

    Rule: take the outcomes whose status is ok or weak (errors and still-pending
    ones are skipped), ordered by when they finished. If the newest is ok, append
    a weak update for it; if it is already weak, write nothing (so marking twice
    is idempotent). Returns that outcome (with tier and model), or None."""
    fin = _finished(read())
    if not fin:
        return None
    last = fin[-1]
    if last["status"] == "ok":
        _append({"ts": round(time.time()), "ref": last["id"], "status": "weak"})
        last.update(status="weak", why="weak")
    return last


def weak_rate(tier, model=None, last=20, days=None):
    """(n_finished, n_weak) over the `last` most recently finished (ok + weak)
    outcomes for `tier` (and `model`, if given), within `days` if given. Errors
    and pending never count."""
    cut = time.time() - days * 86400 if days else None
    fin = [r for r in _finished(read()) if r.get("tier") == tier and (model is None or r.get("model") == model)
           and (cut is None or (r.get("done") or 0) >= cut)]
    fin = fin[-last:] if last else fin
    return len(fin), sum(r["status"] == "weak" for r in fin)


def avoided(days=30, last=20, min_n=3, rate=0.4):
    """Learned routing: every (tier, model) whose finished results from the last
    `days` days (at most the `last` newest) number >= min_n with >= `rate` weak.
    Sorted by tier, model. Expires by itself as weak results age out."""
    if not OUTCOMES.exists():
        return []
    cut = time.time() - days * 86400
    groups = {}
    for r in _finished(read()):
        if r.get("tier") and r.get("model") and (r.get("done") or 0) >= cut:
            groups.setdefault((r["tier"], r["model"]), []).append(r)
    out = []
    for (tier, model), rs in sorted(groups.items()):
        rs = rs[-last:] if last else rs
        w = sum(r["status"] == "weak" for r in rs)
        if len(rs) >= min_n and w and w >= rate * len(rs) - 1e-9:
            out.append({"tier": tier, "model": model, "n": len(rs), "weak": w})
    return out


def learned_lines(av=None):
    """One "  learned: ..." line per avoidance (shared by summary and status)."""
    av = avoided() if av is None else av
    return [f"  learned: {a['tier']} avoids {a['model']} ({a['weak']} of {a['n']} recent results weak)" for a in av]


def forget():
    """Append a reset marker: learning starts fresh, history stays on disk."""
    return _append({"ts": round(time.time()), "reset": True})


def clear():
    try:
        OUTCOMES.unlink()
    except OSError:
        pass


def summary():
    now = time.time()
    rows = [r for r in read() if r["status"] != "pending" or now - (r.get("ts") or 0) < PENDING_TTL]
    if not rows:
        return "outcomes: none recorded yet"
    agg = {}
    for r in rows:
        a = agg.setdefault((r.get("tier") or "T?", r.get("model") or "?"), {s: 0 for s in STATES})
        a[r["status"]] += 1
    running = sum(a["pending"] for a in agg.values())
    head = f"outcomes: {len(rows)} routed subagents" + (f" ({running} still running)" if running else "")
    lines = [head]
    for (tier, model), a in sorted(agg.items()):
        fin = a["ok"] + a["weak"]
        if fin or a["error"]:
            lines.append(f"  {tier} {model}: {fin} finished, {a['weak']} weak, {a['error']} errors")
    lines.extend(learned_lines())
    lines.append("  Only weak results count against a model; errors (limits, outages, denials, interrupts) are neutral.")
    return "\n".join(lines)


def main(argv):
    cmd = argv[0] if argv else "summary"
    if cmd == "weak":
        r = mark_last_weak()
        print("ModelScout: no finished routed subagent recorded yet." if r is None else
              f"ModelScout: noted — the last {r.get('tier') or ''} {r.get('model') or 'subagent'} result was weak.")
        return 0
    if cmd == "forget":
        forget()
        print("ModelScout: learned adjustments cleared.")
        return 0
    print(summary())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
