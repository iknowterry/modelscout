#!/usr/bin/env python3
"""ModelScout savings report — measured from Claude Code transcripts.

For every subagent ModelScout routed (Agent description starting with
"ModelScout:"), it sums the subagent's real token usage (deduplicated per API
message), prices it on the model that actually ran, and compares it with what
the same tokens would have cost on the main session's model.

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
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
CATALOG = Path.home() / ".claude" / "model-catalog.json"
MARKER = re.compile(r"^\s*(⚡\s*)?modelscout\b", re.I)
FAMILY_RANK = {"haiku": 1, "sonnet": 2, "opus": 3, "fable": 4, "mythos": 4}


def family(model):
    low = (model or "").lower()
    for f in FAMILY_RANK:
        if f in low:
            return f
    return None


class Prices:
    def __init__(self):
        self.models = {}
        try:
            cat = json.loads(CATALOG.read_text())
            self.models = cat.get("anthropic", {}).get("models", {}) or {}
        except Exception:
            pass

    def lookup(self, model):
        """Return (price dict per 1M tokens, source label)."""
        m = re.sub(r"-\d{8}$", "", model or "")
        for key in (model, m):
            cost = (self.models.get(key) or {}).get("cost")
            if cost:
                return cost, key
        fam = family(model)
        same = [(v.get("release_date") or "", k, v["cost"]) for k, v in self.models.items()
                if fam and fam in k and v.get("cost")]
        if same:
            _, k, cost = max(same)
            return cost, f"{k} (newest {fam} in catalog)"
        fallback = {"haiku": (1, 5), "sonnet": (3, 15), "opus": (5, 25), "fable": (10, 50), "mythos": (10, 50)}
        i, o = fallback.get(fam, (5, 25))
        return {"input": i, "output": o}, f"built-in {fam or 'default'} estimate"

    def cost(self, model, u):
        p, _ = self.lookup(model)
        pin = p.get("input", 0)
        return (u["input"] * pin + u["output"] * p.get("output", 0)
                + u["cache_write"] * p.get("cache_write", pin * 1.25)
                + u["cache_read"] * p.get("cache_read", pin * 0.1)) / 1e6


def subagent_usage(path):
    seen, u = set(), defaultdict(int)
    model = None
    try:
        for line in path.open():
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
    except Exception:
        return None, None
    return model, dict(u)


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
            model, usage = subagent_usage(sub)
            model = r.get("resolvedModel") or model
            if not usage or not main_model or not model:
                continue
            routes.append({"description": desc, "main": main_model, "routed": model, "usage": usage,
                           "ms": r.get("totalDurationMs") or 0, "session": tr.stem[:8]})
    return routes


def report(routes, prices):
    out = {"routes": len(routes), "down": defaultdict(float), "up": defaultdict(float), "prices": {}}
    down = [r for r in routes if FAMILY_RANK.get(family(r["routed"]), 0) < FAMILY_RANK.get(family(r["main"]), 0)]
    up = [r for r in routes if FAMILY_RANK.get(family(r["routed"]), 0) > FAMILY_RANK.get(family(r["main"]), 0)]
    for label, group in (("down", down), ("up", up)):
        acc = out[label]
        for r in group:
            u = r["usage"]
            acc["tasks"] += 1
            acc["tokens"] += sum(u.values())
            acc["output_tokens"] += u["output"]
            acc["routed_cost"] += prices.cost(r["routed"], u)
            acc["main_cost"] += prices.cost(r["main"], u)
            acc["seconds"] += r["ms"] / 1000
            for m in (r["routed"], r["main"]):
                out["prices"][m] = prices.lookup(m)[1]
    d = out["down"]
    d["saved_cost"] = d["main_cost"] - d["routed_cost"]
    d["saved_pct"] = 100 * d["saved_cost"] / d["main_cost"] if d["main_cost"] else 0.0
    # Main-model tokens freed: the share of the main model's budget those tokens would have used.
    d["main_equiv_tokens_saved"] = d["tokens"] * d["saved_pct"] / 100
    out["by_pair"] = defaultdict(int)
    for r in down + up:
        out["by_pair"][f"{family(r['main'])} -> {family(r['routed'])}"] += 1
    out["same_tier_skipped"] = len(routes) - len(down) - len(up)
    return out


def fmt_tokens(n):
    return f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.1f}K" if n >= 1e3 else str(int(n))


def render_text(o, days):
    d, u = o["down"], o["up"]
    lines = [f"🔭 ModelScout savings — last {days} days",
             f"Routed down to lighter models: {int(d['tasks'])} task(s), {fmt_tokens(d['tokens'])} tokens, "
             f"{d['seconds']/60:.1f} min of subagent time"]
    if d["tasks"]:
        lines += [f"  Saved: {d['saved_pct']:.0f}% of what the main model would have used "
                  f"(≈ ${d['saved_cost']:.2f} at API prices; ${d['routed_cost']:.2f} vs ${d['main_cost']:.2f})",
                  f"  Main-model budget freed: ≈ {fmt_tokens(d['main_equiv_tokens_saved'])} tokens' worth"]
    if u["tasks"]:
        lines.append(f"Routed up for hard work: {int(u['tasks'])} task(s), "
                     f"+${u['main_cost'] and (u['routed_cost'] - u['main_cost']):.2f} invested in a stronger model")
    if o["by_pair"]:
        lines.append("Routes: " + ", ".join(f"{k} ×{v}" for k, v in o["by_pair"].items()))
    if o["same_tier_skipped"]:
        lines.append(f"({o['same_tier_skipped']} same-tier subagent(s) not counted)")
    lines.append("Prices: " + "; ".join(f"{m} → {src}" for m, src in o["prices"].items()) if o["prices"] else
                 "No routed subagents found yet.")
    lines.append("Assumes the main model would have used the same tokens. Subscribers: the % is the share "
                 "of usage-limit quota freed.")
    return "\n".join(lines)


def render_markdown(o, days):
    d = o["down"]
    return "\n".join([
        f"| Measured over {days} days | Value |", "|---|---|",
        f"| Tasks routed to lighter models | {int(d['tasks'])} |",
        f"| Tokens handled by lighter models | {fmt_tokens(d['tokens'])} |",
        f"| Saved vs. main model | **{d['saved_pct']:.0f}%** (${d['saved_cost']:.2f} at API prices) |",
        f"| Main-model budget freed | ≈ {fmt_tokens(d['main_equiv_tokens_saved'])} tokens |",
        f"| Subagent run time (measured) | {d['seconds']/60:.1f} min |",
    ])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--all", action="store_true", help="count every subagent, not only ModelScout routes")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()
    o = report(scan(a.days, a.all), Prices())
    if a.json:
        print(json.dumps(o, indent=2, default=dict))
    elif a.markdown:
        print(render_markdown(o, a.days))
    else:
        print(render_text(o, a.days))


if __name__ == "__main__":
    sys.exit(main())
