#!/usr/bin/env python3
"""ModelScout savings report — measured from real agent logs.

Sources: Claude Code transcripts (~/.claude/projects) and Hermes Agent's session
database (~/.hermes/state.db, read-only). For every subagent ModelScout routed
(task description starting with "ModelScout:"), it sums the subagent's real
token usage, prices it on the model that actually ran, and compares it with
what the same tokens would have cost on the main session's model.

Usage:
  savings.py                 # text report, last 30 days
  savings.py --days 7
  savings.py --all           # include every subagent, not only ModelScout routes
  savings.py --json | --markdown

Assumption (stated in every report): the main model would have used the same
number of tokens. Time is the measured subagent run time; no counterfactual
time is invented.
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
HERMES_DB = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "state.db"
MARKER = re.compile(r"^\s*(⚡\s*)?modelscout\b", re.I)
FAMILY_RANK = {"haiku": 1, "sonnet": 2, "opus": 3, "fable": 4, "mythos": 4}


def family(model):
    low = (model or "").lower()
    for f in FAMILY_RANK:
        if f in low:
            return f
    return None


def _catalog():
    """The shared catalog loader (catalog.py beside this script), loaded by path."""
    import importlib.util
    name = "modelscout_catalog"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("catalog.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


class Prices:
    def __init__(self):
        self.models, self.all = {}, {}
        try:
            cat = _catalog().load()
            self.models = cat.get("anthropic", {}).get("models", {}) or {}
            for prov in cat.values():
                for k, v in ((prov or {}).get("models") or {}).items():
                    if isinstance(v, dict) and v.get("cost"):
                        self.all.setdefault(k, v)
        except Exception:
            pass

    def _find(self, model):
        """Return (price dict, tiers list, source label) for a model."""
        bare = (model or "").split("/")[-1]
        m = re.sub(r"-\d{8}$", "", bare)
        for key in (model, bare, m):
            e = self.models.get(key) or self.all.get(key) or {}
            if e.get("cost"):
                return e["cost"], e.get("tiers") or e["cost"].get("tiers") or [], key
        fam = family(model)
        same = [(v.get("release_date") or "", k, v) for k, v in self.models.items()
                if fam and fam in k and v.get("cost")]
        if same:
            _, k, v = max(same, key=lambda t: t[:2])
            return v["cost"], v.get("tiers") or v["cost"].get("tiers") or [], f"{k} (newest {fam} in catalog)"
        fallback = {"haiku": (1, 5), "sonnet": (3, 15), "opus": (5, 25), "fable": (10, 50), "mythos": (10, 50)}
        i, o = fallback.get(fam, (5, 25))
        return {"input": i, "output": o}, [], f"built-in {fam or 'default'} estimate"

    def lookup(self, model):
        """Return (price dict per 1M tokens, source label)."""
        p, _, label = self._find(model)
        return p, label

    def tiered(self, model):
        return any(isinstance(t, dict) and (t.get("tier") or {}).get("size") for t in self._find(model)[1])

    def rank(self, model):
        """Comparable price level: output price per 1M tokens."""
        return self.lookup(model)[0].get("output", 0) or 0

    @staticmethod
    def _price(p, u):
        pin = p.get("input", 0)
        return (u["input"] * pin + u["output"] * p.get("output", 0)
                + u["cache_write"] * p.get("cache_write", pin * 1.25)
                + u["cache_read"] * p.get("cache_read", pin * 0.1)) / 1e6

    def cost(self, model, u):
        """Base-price cost of one usage total (no tiers)."""
        return self._price(self.lookup(model)[0], u)

    def call_cost(self, model, u):
        """Cost of ONE API request: the highest context tier its prompt size exceeds applies."""
        p, tiers, _ = self._find(model)
        prompt = u.get("input", 0) + u.get("cache_read", 0) + u.get("cache_write", 0)
        best, size = None, -1
        for t in tiers:
            try:
                n = (t.get("tier") or {}).get("size")
                if (t.get("tier") or {}).get("type", "context") == "context" and n is not None and prompt > n > size:
                    best, size = t, n
            except Exception:
                continue
        if best:
            p = {**p, **{k: v for k, v in best.items() if k in ("input", "output", "cache_read", "cache_write")}}
            if "input" in best:  # cache prices the base lacks derive from the tier's own input
                for k, f in (("cache_write", 1.25), ("cache_read", 0.1)):
                    if k not in p:
                        p[k] = best["input"] * f
        return self._price(p, u)

    def route_cost(self, model, r):
        """A route's cost: per request when its calls are known, else base pricing on the total."""
        if r.get("calls"):
            return sum(self.call_cost(model, c) for c in r["calls"])
        return self.cost(model, r["usage"])


def _ts(value):
    try:
        from datetime import datetime
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def subagent_usage(path, calls=None):
    """Token usage (deduplicated per API message), model, and wall time from a subagent log.
    If `calls` is a list, each message's own usage dict is appended to it (for per-request tiers)."""
    seen, u = set(), defaultdict(int)
    model, first, last = None, None, None
    try:
        for line in path.open():
            m = re.search(r'"timestamp":"([^"]+)"', line)
            t = _ts(m.group(1)) if m else None
            if t:
                first = t if first is None else min(first, t)
                last = t if last is None else max(last, t)
            if '"assistant"' not in line:
                continue
            d = json.loads(line)
            msg = d.get("message") or {}
            if d.get("type") != "assistant" or msg.get("id") in seen or not msg.get("usage"):
                continue
            seen.add(msg.get("id"))
            us = msg["usage"]
            model = msg.get("model") or model
            u["input"] += us.get("input_tokens", 0) or 0
            u["output"] += us.get("output_tokens", 0) or 0
            u["cache_write"] += us.get("cache_creation_input_tokens", 0) or 0
            u["cache_read"] += us.get("cache_read_input_tokens", 0) or 0
            if calls is not None:
                calls.append({"input": us.get("input_tokens", 0) or 0, "output": us.get("output_tokens", 0) or 0,
                              "cache_write": us.get("cache_creation_input_tokens", 0) or 0,
                              "cache_read": us.get("cache_read_input_tokens", 0) or 0})
    except Exception:
        return None, None, 0
    ms = int((last - first) * 1000) if first and last else 0
    return model, dict(u), ms


def scan(days, include_all):
    cutoff = time.time() - days * 86400
    routes = []
    for tr in PROJECTS.glob("*/*.jsonl"):
        try:
            if tr.stat().st_mtime < cutoff:
                continue
            lines = tr.open().read().splitlines()
        except Exception:
            continue
        main_model, descriptions = None, {}
        for line in lines:
            if '"model"' not in line and '"toolUseResult"' not in line and '"Agent"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            if d.get("type") == "assistant" and not d.get("isSidechain"):
                if msg.get("model") and msg["model"] != "<synthetic>":
                    main_model = msg["model"]
                for c in msg.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") in ("Agent", "Task"):
                        descriptions[c.get("id")] = (c.get("input") or {}).get("description", "")
            r = d.get("toolUseResult")
            if not (isinstance(r, dict) and r.get("agentId")):
                continue
            tool_use_id = next((c.get("tool_use_id") for c in (msg.get("content") or [])
                                if isinstance(c, dict) and c.get("tool_use_id")), None)
            desc = descriptions.get(tool_use_id, "")
            if not include_all and not MARKER.match(desc or ""):
                continue
            sub = tr.parent / tr.stem / "subagents" / f"agent-{r['agentId']}.jsonl"
            calls = []
            model, usage, log_ms = subagent_usage(sub, calls)
            model = r.get("resolvedModel") or model
            if not usage or not main_model or not model:
                continue
            routes.append({"description": desc, "main": main_model, "routed": model, "usage": usage,
                           "ms": r.get("totalDurationMs") or log_ms, "session": tr.stem[:8],
                           "host": "claude-code", "calls": calls})
    return routes


def scan_hermes(days, include_all, db=HERMES_DB):
    """Delegated child sessions from Hermes's state.db (read-only)."""
    import sqlite3
    if not Path(db).exists():
        return []
    cutoff = time.time() - days * 86400
    routes = []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT c.id, c.model, p.model, c.started_at, c.ended_at, c.title, "
            "c.input_tokens, c.output_tokens, c.cache_read_tokens, c.cache_write_tokens "
            "FROM sessions c JOIN sessions p ON p.id = c.parent_session_id "
            "WHERE c.started_at >= ?", (cutoff,)).fetchall()
        for sid, cmodel, pmodel, start, end, title, ti, to, tcr, tcw in rows:
            first = con.execute("SELECT content FROM messages WHERE session_id = ? AND role = 'user' "
                                "ORDER BY rowid LIMIT 1", (sid,)).fetchone()
            goal = first[0] if first and isinstance(first[0], str) else ""
            # Hermes titles children "Subagent: <goal>"; the goal itself is the first user message.
            clean_title = re.sub(r"^\s*subagent\s*:\s*", "", title or "", flags=re.I)
            desc = goal or clean_title
            if not include_all and not (MARKER.match(clean_title) or MARKER.match(goal)):
                continue
            usage_rows = con.execute(
                "SELECT model, SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens), "
                "SUM(cache_write_tokens) FROM session_model_usage WHERE session_id = ? GROUP BY model",
                (sid,)).fetchall() or [(cmodel, ti, to, tcr, tcw)]
            for model, i, o, cr, cw in usage_rows:
                if not model or not pmodel:
                    continue
                routes.append({"description": desc[:80], "main": pmodel, "routed": model,
                               "usage": {"input": i or 0, "output": o or 0, "cache_read": cr or 0,
                                         "cache_write": cw or 0},
                               "ms": int(((end or start) - start) * 1000) if start else 0,
                               "session": sid[:12], "host": "hermes"})
        con.close()
    except Exception:
        return routes
    return routes


def report(routes, prices):
    out = {"routes": len(routes), "down": defaultdict(float), "up": defaultdict(float), "prices": {}}
    down = [r for r in routes if prices.rank(r["routed"]) < prices.rank(r["main"])]
    up = [r for r in routes if prices.rank(r["routed"]) > prices.rank(r["main"])]
    for label, group in (("down", down), ("up", up)):
        acc = out[label]
        for r in group:
            u = r["usage"]
            acc["tasks"] += 1
            acc["tokens"] += sum(u.values())
            acc["output_tokens"] += u["output"]
            acc["routed_cost"] += prices.route_cost(r["routed"], r)
            acc["main_cost"] += prices.route_cost(r["main"], r)
            acc["seconds"] += r["ms"] / 1000
            for m in (r["routed"], r["main"]):
                out["prices"][m] = prices.lookup(m)[1]
    out["tiered"] = any(prices.tiered(m) for m in out["prices"])
    d = out["down"]
    d["saved_cost"] = d["main_cost"] - d["routed_cost"]
    d["saved_pct"] = 100 * d["saved_cost"] / d["main_cost"] if d["main_cost"] else 0.0
    # Main-model tokens freed: the share of the main model's budget those tokens would have used.
    d["main_equiv_tokens_saved"] = d["tokens"] * d["saved_pct"] / 100
    out["by_pair"] = defaultdict(int)
    for r in down + up:
        short = lambda m: family(m) or (m or "?").split("/")[-1]
        out["by_pair"][f"{short(r['main'])} -> {short(r['routed'])}"] += 1
    out["same_tier_skipped"] = len(routes) - len(down) - len(up)
    return out


def fmt_time(seconds):
    return f"{seconds:.0f}s" if seconds < 60 else f"{seconds/60:.1f} min"


def fmt_tokens(n):
    return f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.1f}K" if n >= 1e3 else str(int(n))


def render_text(o, days):
    d, u = o["down"], o["up"]
    lines = [f"🔭 ModelScout savings — last {days} days",
             f"Routed down to lighter models: {int(d['tasks'])} task(s), {fmt_tokens(d['tokens'])} tokens, "
             f"{fmt_time(d['seconds'])} of subagent time"]
    if d["tasks"]:
        lines += [f"  Saved: {d['saved_pct']:.0f}% of what the main model would have used "
                  f"(≈ ${d['saved_cost']:.2f} at API prices; ${d['routed_cost']:.2f} vs ${d['main_cost']:.2f})",
                  f"  Main-model budget freed: ≈ {fmt_tokens(d['main_equiv_tokens_saved'])} tokens' worth"]
    if u["tasks"]:
        lines.append(f"Routed up for hard work: {int(u['tasks'])} task(s), "
                     f"+${u['main_cost'] and (u['routed_cost'] - u['main_cost']):.2f} invested in a stronger model")
    if o["by_pair"]:
        lines.append("Routes: " + ", ".join(f"{k} ×{v}" for k, v in o["by_pair"].items()))
    if o.get("hosts"):
        lines.append("Sources: " + ", ".join(o["hosts"]))
    if o["same_tier_skipped"]:
        lines.append(f"({o['same_tier_skipped']} same-tier subagent(s) not counted)")
    lines.append("Prices: " + "; ".join(f"{m} → {src}" for m, src in o["prices"].items()) if o["prices"] else
                 "No routed subagents found yet.")
    lines.append("Assumes the main model would have used the same tokens. Subscribers: the % is the share "
                 "of usage-limit quota freed."
                 + (" Context-tiered prices applied per request for Claude Code subagents." if o.get("tiered") else ""))
    return "\n".join(lines)


def render_markdown(o, days):
    d = o["down"]
    return "\n".join([
        f"| Measured over {days} days | Value |", "|---|---|",
        f"| Tasks routed to lighter models | {int(d['tasks'])} |",
        f"| Tokens handled by lighter models | {fmt_tokens(d['tokens'])} |",
        f"| Saved vs. main model | **{d['saved_pct']:.0f}%** (${d['saved_cost']:.2f} at API prices) |",
        f"| Main-model budget freed | ≈ {fmt_tokens(d['main_equiv_tokens_saved'])} tokens |",
        f"| Subagent run time (measured) | {fmt_time(d['seconds'])} |",
    ])


def text_report(days=30, include_all=False, markdown=False):
    """Scan every source and return the rendered report (used by the Hermes plugin)."""
    routes = scan(days, include_all) + scan_hermes(days, include_all)
    o = report(routes, Prices())
    o["hosts"] = sorted({r.get("host", "claude-code") for r in routes})
    return render_markdown(o, days) if markdown else render_text(o, days)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--all", action="store_true", help="count every subagent, not only ModelScout routes")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()
    routes = scan(a.days, a.all) + scan_hermes(a.days, a.all)
    o = report(routes, Prices())
    o["hosts"] = sorted({r.get("host", "claude-code") for r in routes})
    if a.json:
        print(json.dumps(o, indent=2, default=dict))
    elif a.markdown:
        print(render_markdown(o, a.days))
    else:
        print(render_text(o, a.days))


if __name__ == "__main__":
    sys.exit(main())
