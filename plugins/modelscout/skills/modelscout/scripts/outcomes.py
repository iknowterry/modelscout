#!/usr/bin/env python3
"""ModelScout outcomes: did each routed subagent get the job done?

One JSON line per routed subagent in ~/.claude/modelscout-outcomes.jsonl:
  {"id", "ts", "host", "tier", "model", "status": "ok"|"fail", "why"}
No goal text, prompts or output are stored. Records come from:
- Hermes: the subagent_stop hook (child status: completed / failed / interrupted).
- Claude Code: the PostToolUse hook on the Agent tool.
- The user: `modelscout: weak` marks the latest outcome as a failure, and the
  main model runs `outcomes.py weak` when it had to redo a subagent's work.

Usage:
  outcomes.py weak       # mark the latest outcome as a failure
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


def tier_from(text):
    """"ModelScout: T1 · rename …" → "T1"; None when untagged."""
    m = TAG.match(text or "")
    return m.group(1).upper() if m else None


def is_routed(text):
    return bool(MARK.match(text or ""))


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


def record(host, tier, model, status, why=""):
    """Record one routed subagent. status: "ok" or "fail"."""
    return _append({"id": secrets.token_hex(4), "ts": round(time.time()), "host": host,
                    "tier": tier if tier in ("T1", "T2", "T3", "T4") else None,
                    "model": (model or None), "status": "fail" if status == "fail" else "ok",
                    "why": why or ""})


def read():
    """Outcomes oldest first, with later verdicts (`weak`) folded in."""
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
        if r.get("verdict") and r.get("ref") in by_id:
            by_id[r["ref"]].update(status=r["verdict"], why=r.get("why") or "weak")
        elif r.get("id") and r.get("status") in ("ok", "fail"):
            by_id[r["id"]] = r
            out.append(r)
    return out


def mark_last_weak(why="weak"):
    """Mark the latest outcome as a failure. Returns the outcome or None."""
    rows = read()
    if not rows:
        return None
    last = rows[-1]
    if last["status"] != "fail":
        _append({"ts": round(time.time()), "ref": last["id"], "verdict": "fail", "why": why})
        last.update(status="fail", why=why)
    return last


def clear():
    try:
        OUTCOMES.unlink()
    except OSError:
        pass


def summary():
    rows = read()
    if not rows:
        return "outcomes: none recorded yet"
    agg = {}
    for r in rows:
        k = (r.get("tier") or "T?", r.get("model") or "?")
        a = agg.setdefault(k, [0, 0])
        a[0] += 1
        a[1] += r["status"] == "fail"
    lines = [f"outcomes: {len(rows)} routed subagents"]
    for (tier, model), (n, f) in sorted(agg.items()):
        lines.append(f"  {tier} {model}: {n - f} ok, {f} weak or failed")
    return "\n".join(lines)


def main(argv):
    cmd = argv[0] if argv else "summary"
    if cmd == "weak":
        r = mark_last_weak()
        print("ModelScout: no routed subagent recorded yet." if r is None else
              f"ModelScout: noted — the last {r.get('tier') or ''} {r.get('model') or 'subagent'} result was weak.")
        return 0
    print(summary())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
