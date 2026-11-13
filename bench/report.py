#!/usr/bin/env python3
"""Turn a bench/results/<run> folder into a Markdown results table.

Only VALID runs count (see run.py). Savings are computed on paired tasks only
(tasks with valid runs in both arms), from mean cost per task, so a task that
failed to run in one arm can't flatter the other. Pass rates are shown next to
cost: a saving that comes with lower quality is visible, not hidden.

Usage: python3 bench/report.py bench/results/<run> [--json]
Writes summary.md (and summary.json) into the run folder and prints the table.
"""
import json
import statistics
import sys
from pathlib import Path

TIER_NAMES = {"T1": "mechanical", "T2": "standard", "T3": "hard"}


def load(run):
    recs = []
    for p in sorted(Path(run).glob("*--*--*.json")):
        try:
            recs.append(json.loads(p.read_text()))
        except ValueError:
            pass
    meta = {}
    try:
        meta = json.loads((Path(run) / "meta.json").read_text())
    except (OSError, ValueError):
        pass
    return meta, recs


def mean(xs):
    return statistics.fmean(xs) if xs else None


def summarize(recs):
    valid = [r for r in recs if r.get("valid") and r.get("usage")]
    by_task = {}
    for r in valid:
        t = by_task.setdefault(r["task"], {"tier": r["tier"], "baseline": [], "routed": []})
        t[r["arm"]].append(r)
    rows = []
    for tid, t in sorted(by_task.items(), key=lambda kv: (kv[1]["tier"], kv[0])):
        row = {"task": tid, "tier": t["tier"]}
        for arm in ("baseline", "routed"):
            rs = t[arm]
            row[arm] = {"runs": len(rs), "cost": mean([r["usage"]["cost"] for r in rs]),
                        "pass": sum(bool(r["passed"]) for r in rs), "wall": mean([r["wall_s"] for r in rs]),
                        "subagents": mean([len(r["usage"]["agent_calls"]) for r in rs])}
        row["paired"] = bool(t["baseline"] and t["routed"])
        if row["paired"] and row["baseline"]["cost"]:
            row["saved"] = 1 - row["routed"]["cost"] / row["baseline"]["cost"]
        rows.append(row)
    paired = [r for r in rows if r["paired"]]

    def agg(rs):
        b = sum(r["baseline"]["cost"] for r in rs)
        o = sum(r["routed"]["cost"] for r in rs)
        bp = sum(r["baseline"]["pass"] for r in rs)
        bn = sum(r["baseline"]["runs"] for r in rs)
        op = sum(r["routed"]["pass"] for r in rs)
        on = sum(r["routed"]["runs"] for r in rs)
        return {"tasks": len(rs), "baseline_cost": b, "routed_cost": o, "saved": (1 - o / b) if b else None,
                "baseline_pass": bp, "baseline_runs": bn, "routed_pass": op, "routed_runs": on,
                "baseline_wall": sum(r["baseline"]["wall"] or 0 for r in rs),
                "routed_wall": sum(r["routed"]["wall"] or 0 for r in rs)}
    tiers = {tier: agg([r for r in paired if r["tier"] == tier]) for tier in sorted({r["tier"] for r in paired})}
    # where the routed arm's money went: main model vs subagent models
    spend = {}
    for r in valid:
        if r["arm"] != "routed":
            continue
        for m, u in r["usage"]["per_model"].items():
            spend[m] = spend.get(m, 0) + u["cost"]
    regressions = [r["task"] for r in paired
                   if r["routed"]["pass"] / r["routed"]["runs"] < r["baseline"]["pass"] / r["baseline"]["runs"]]
    return {"rows": rows, "tiers": tiers, "total": agg(paired) if paired else None, "routed_spend": spend,
            "invalid": [f"{r['task']} {r['arm']} #{r['n']}: {'; '.join(r.get('problems') or [])}"
                        for r in recs if not r.get("valid")],
            "regressions": regressions}


def pct(x):
    return "–" if x is None else f"{x * 100:.0f}%"


def usd(x):
    return "–" if x is None else f"${x:.2f}"


def markdown(meta, s):
    out = ["# ModelScout benchmark results", ""]
    if meta:
        out += [f"Main model `{meta.get('model')}` · ModelScout {meta.get('plugin_version')} · "
                f"{meta.get('claude_version')} · {meta.get('repeat')} run(s) per task and arm · started {meta.get('started')}", ""]
    t = s["total"]
    if not t:
        return "\n".join(out + ["No paired valid runs yet."])
    out += [f"**Overall:** {usd(t['baseline_cost'])} → {usd(t['routed_cost'])} over {t['tasks']} tasks "
            f"(**{pct(t['saved'])} less**). Pass rate {t['baseline_pass']}/{t['baseline_runs']} without "
            f"ModelScout, {t['routed_pass']}/{t['routed_runs']} with it.", "",
            "| Tier | Tasks | Without ModelScout | With ModelScout | Saved | Pass (without → with) |",
            "|---|---|---|---|---|---|"]
    for tier, a in s["tiers"].items():
        out.append(f"| {tier} {TIER_NAMES.get(tier, '')} | {a['tasks']} | {usd(a['baseline_cost'])} | "
                   f"{usd(a['routed_cost'])} | {pct(a['saved'])} | {a['baseline_pass']}/{a['baseline_runs']} → "
                   f"{a['routed_pass']}/{a['routed_runs']} |")
    out += ["", "| Task | Tier | Without | With | Saved | Pass without | Pass with | Subagents (with) |",
            "|---|---|---|---|---|---|---|---|"]
    for r in s["rows"]:
        b, o = r["baseline"], r["routed"]
        subs = "–" if o["subagents"] is None else f"{o['subagents']:.1f}"
        out.append(f"| {r['task']} | {r['tier']} | {usd(b['cost'])} | {usd(o['cost'])} | "
                   f"{pct(r.get('saved'))} | {b['pass']}/{b['runs']} | {o['pass']}/{o['runs']} | {subs} |")
    if s["routed_spend"]:
        tot = sum(s["routed_spend"].values()) or 1
        out += ["", "Where the money went with ModelScout: " + ", ".join(
            f"`{m}` {v / tot * 100:.0f}%" for m, v in sorted(s["routed_spend"].items(), key=lambda kv: -kv[1]))]
    if s["regressions"]:
        out += ["", "Quality regressions (lower pass rate with ModelScout): " + ", ".join(s["regressions"])]
    if s["invalid"]:
        out += ["", "Excluded invalid runs: " + "; ".join(s["invalid"])]
    out += ["", "Method: same tasks, same main model, fresh copy of the sample project per run; "
            "cost = every API request in the main session and its subagents, priced per request "
            "with models.dev prices (identical for both arms), so the main model's briefing and "
            "checking are included. Pass = hidden tests and the project's own tests both pass."]
    return "\n".join(out)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    run = Path(argv[0])
    meta, recs = load(run)
    s = summarize(recs)
    md = markdown(meta, s)
    (run / "summary.md").write_text(md + "\n")
    (run / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, indent=1, default=str) if "--json" in argv else md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
