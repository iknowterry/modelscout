#!/usr/bin/env python3
"""ModelScout benchmark runner: the same tasks, with ModelScout off and on.

Each run copies bench/fixture into a fresh temp directory, overlays the task's
setup/, runs headless Claude Code (`claude -p`) on the task prompt, then copies
in the task's hidden check/ tests and runs them together with the project's own
tests. Cost is measured from the session transcripts (main session + every
subagent), each API request priced by the model that served it, with the same
models.dev prices for both arms, so the comparison is net: the main model's
briefing and checking work in the routed arm is counted.

Arms
  baseline  ModelScout not loaded. The main model does everything.
  routed    ModelScout loaded from this repo (plugins/modelscout), mode auto.

Isolation
  - Both arms run with --setting-sources project and --strict-mcp-config, so
    your installed plugins, user hooks and MCP servers are not loaded; only the
    routed arm adds --plugin-dir plugins/modelscout. A run is marked INVALID if
    the baseline transcript contains ModelScout's block or the routed one lacks it.
  - MODELSCOUT_STATE_DIR points ModelScout's settings and outcome log at the
    run's own folder, so your real settings and learning are untouched.
  - Work happens in a temp copy whose path contains "modelscout-bench"; your
    `modelscout: savings` report skips those sessions.
  - Permissions: edits are auto-accepted. Bash may only run the tests
    (`python3 -m unittest`, `pytest`) and ls/wc/diff; anything else is refused in
    headless mode. Web tools, curl/wget, git, ssh, rm and sudo are denied. This is
    an allowlist, not a sandbox: for stronger isolation run it in a container.

This spends real tokens (your subscription quota or API credit). Without --go
it only prints the plan.

Usage
  python3 bench/run.py                       # plan only, spends nothing
  python3 bench/run.py --go                  # all tasks, both arms, once
  python3 bench/run.py --go --repeat 3 --model opus --tasks t1-rename,t3-money
  python3 bench/report.py bench/results/<run>   # the table
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

BENCH = Path(__file__).resolve().parent
REPO = BENCH.parent
PLUGIN = REPO / "plugins" / "modelscout"
TASKS = BENCH / "tasks"
FIXTURE = BENCH / "fixture"
PROJECTS = Path.home() / ".claude" / "projects"
ARMS = ("baseline", "routed")
# Bash is limited to running the tests and to read-only listing/diffing: no
# generic `python3 *` (arbitrary code), no `find` (-exec), no network tools.
ALLOWED = ["Read", "Edit", "Write", "Glob", "Grep", "Agent", "Task", "TodoWrite",
           "Bash(python3 -m unittest*)", "Bash(python3 -m pytest*)", "Bash(pytest*)",
           "Bash(ls*)", "Bash(wc*)", "Bash(diff*)"]
DENIED = ["WebFetch", "WebSearch", "Bash(curl*)", "Bash(wget*)", "Bash(git*)", "Bash(ssh*)",
          "Bash(rm*)", "Bash(sudo*)"]
GUARD = ("Work only inside the current directory. Don't use git, the network, or any path outside it. "
         "When you are done, stop; don't ask follow-up questions.")
MARK = "<modelscout host="


def load_tasks(only=None):
    tasks = []
    for p in sorted(TASKS.glob("*/task.json")):
        t = json.loads(p.read_text())
        t["dir"] = p.parent
        if not only or t["id"] in only:
            tasks.append(t)
    return tasks


def overlay(src, dst):
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def prepare(task, root):
    proj = root / "project"
    shutil.copytree(FIXTURE, proj, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    overlay(task["dir"] / "setup", proj)
    state = root / "state"
    state.mkdir()
    (state / "modelscout-profile.json").write_text(json.dumps({"mode": "auto"}))
    return proj, state


def claude_cmd(task, arm, model):
    cmd = ["claude", "-p", task["prompt"] + "\n\n" + GUARD, "--model", model, "--output-format", "json",
           "--setting-sources", "project", "--strict-mcp-config", "--permission-mode", "acceptEdits",
           "--settings", json.dumps({"enabledPlugins": {"modelscout@modelscout": False}}),  # installed copy off in both arms
           "--allowedTools", *ALLOWED, "--disallowedTools", *DENIED]
    if arm == "routed":
        weak = PLUGIN / "skills" / "modelscout" / "scripts" / "outcomes.py"
        cmd += ["--plugin-dir", str(PLUGIN),  # and the one script the card rules may run: marking a weak result
                "--allowedTools", f'Bash(python3 "{weak}" weak)', f"Bash(python3 {weak} weak)"]
    return cmd


def run_check(proj, task):
    """Hidden check + the project's own tests. Returns (passed, detail)."""
    chk = proj / "_bench_check"
    if chk.exists():
        shutil.rmtree(chk)  # the agent must not pre-seed the hidden tests
    shutil.copytree(task["dir"] / "check", chk)
    res = {}
    for name, args in (("hidden", ["-s", "_bench_check", "-t", "."]), ("visible", ["-s", "tests", "-t", "."])):
        try:
            p = subprocess.run([sys.executable, "-m", "unittest", "discover", *args], cwd=proj,
                               capture_output=True, text=True, timeout=300)
            res[name] = {"ok": p.returncode == 0, "tail": (p.stderr or p.stdout)[-600:]}
        except subprocess.TimeoutExpired:
            res[name] = {"ok": False, "tail": "timeout"}
    return res["hidden"]["ok"] and res["visible"]["ok"], res


def find_transcript(session_id):
    hits = list(PROJECTS.glob(f"*/{session_id}.jsonl")) if session_id else []
    return hits[0] if hits else None


def _prices():
    sys.path.insert(0, str(PLUGIN / "skills" / "modelscout" / "scripts"))
    import savings  # noqa: E402
    return savings.Prices()


def measure(transcript, prices):
    """Per-model tokens and cost over the main transcript and all its subagent
    transcripts. Each API message counts once (deduplicated by message id) and
    is priced per request by its own model."""
    files = [transcript] + sorted((transcript.parent / transcript.stem / "subagents").glob("*.jsonl"))
    seen, per_model, text_has_mark, routed = set(), {}, False, []
    for f in files:
        try:
            lines = f.read_text().splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            att = d.get("attachment") if isinstance(d.get("attachment"), dict) else {}
            if (f == transcript and att.get("type") == "hook_additional_context"
                    and MARK in str(att.get("content"))):  # injected by ModelScout's prompt hook, not merely mentioned
                text_has_mark = True
            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            if f == transcript and d.get("type") == "assistant":
                for c in msg.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") in ("Agent", "Task"):
                        ti = c.get("input") or {}
                        routed.append({"description": str(ti.get("description", ""))[:80], "model": ti.get("model")})
            if d.get("type") != "assistant" or not msg.get("usage") or msg.get("id") in seen:
                continue
            model = msg.get("model")
            if not model or model == "<synthetic>":
                continue
            seen.add(msg.get("id"))
            us = msg["usage"]
            u = {"input": us.get("input_tokens", 0) or 0, "output": us.get("output_tokens", 0) or 0,
                 "cache_write": us.get("cache_creation_input_tokens", 0) or 0,
                 "cache_read": us.get("cache_read_input_tokens", 0) or 0}
            m = per_model.setdefault(model, {"requests": 0, "cost": 0.0, **{k: 0 for k in u}})
            m["requests"] += 1
            m["cost"] += prices.call_cost(model, u)
            for k, v in u.items():
                m[k] += v
    total = sum(m["cost"] for m in per_model.values())
    return {"per_model": per_model, "cost": round(total, 6), "has_block": text_has_mark,
            "subagent_files": len(files) - 1, "agent_calls": routed}


def outcomes_of(state):
    p = state / "modelscout-outcomes.jsonl"
    try:
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


def one_run(task, arm, model, n, out_dir, prices, keep):
    root = Path(tempfile.mkdtemp(prefix=f"modelscout-bench-{task['id']}-{arm}-"))
    proj, state = prepare(task, root)
    env = dict(os.environ, MODELSCOUT_STATE_DIR=str(state))
    env.pop("CLAUDECODE", None)  # a nested claude must not think it is inside this session
    t0 = time.time()
    timeout = int(task.get("timeout_min", 20)) * 60
    rec = {"task": task["id"], "tier": task["tier"], "arm": arm, "model": model, "n": n,
           "started": datetime.now().isoformat(timespec="seconds")}
    try:
        p = subprocess.run(claude_cmd(task, arm, model), cwd=proj, env=env, capture_output=True,
                           text=True, timeout=timeout)
        rec["exit"] = p.returncode
        try:
            j = json.loads(p.stdout)
        except ValueError:
            j = {}
        rec["session_id"] = j.get("session_id")
        rec["claude_reported_cost"] = j.get("total_cost_usd")
        rec["is_error"] = j.get("is_error")
        rec["num_turns"] = j.get("num_turns")
        if not j:
            rec["stderr_tail"] = (p.stderr or p.stdout)[-600:]
    except subprocess.TimeoutExpired:
        rec["exit"] = "timeout"
    rec["wall_s"] = round(time.time() - t0, 1)
    rec["passed"], rec["checks"] = run_check(proj, task)
    tr = find_transcript(rec.get("session_id"))
    rec["transcript"] = str(tr) if tr else None
    rec["usage"] = measure(tr, prices) if tr else None
    rec["outcomes"] = outcomes_of(state)
    problems = []
    if not tr:
        problems.append("no transcript found")
    elif arm == "baseline" and rec["usage"]["has_block"]:
        problems.append("ModelScout block present in the baseline arm")
    elif arm == "routed" and not rec["usage"]["has_block"]:
        problems.append("ModelScout block missing in the routed arm (plugin did not load)")
    rec["valid"] = not problems
    rec["problems"] = problems
    (out_dir / f"{task['id']}--{arm}--{n}.json").write_text(json.dumps(rec, indent=1))
    if not keep:
        shutil.rmtree(root, ignore_errors=True)
    else:
        rec["workdir"] = str(root)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true", help="actually run (spends tokens)")
    ap.add_argument("--model", default="opus", help="main-session model for both arms (default opus)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    ap.add_argument("--arms", default="baseline,routed")
    ap.add_argument("--keep", action="store_true", help="keep the temp project copies")
    ap.add_argument("--seed", type=int, default=None, help="order shuffle seed")
    a = ap.parse_args(argv)
    tasks = load_tasks([x for x in a.tasks.split(",") if x])
    arms = [x for x in a.arms.split(",") if x in ARMS]
    if not tasks or not arms:
        print("No tasks or arms selected.")
        return 2
    plan = [(t, arm, n) for n in range(1, a.repeat + 1) for t in tasks for arm in arms]
    rnd = random.Random(a.seed)
    rnd.shuffle(plan)  # interleave arms so time-of-day and rate limits hit both alike
    tiers = {}
    for t in tasks:
        tiers[t["tier"]] = tiers.get(t["tier"], 0) + 1
    print(f"Plan: {len(tasks)} tasks ({', '.join(f'{k}×{v}' for k, v in sorted(tiers.items()))}) × "
          f"{len(arms)} arms × {a.repeat} = {len(plan)} headless Claude Code runs, main model {a.model}.")
    if not a.go:
        print("Nothing run. Add --go to run it (this spends real tokens / usage quota).")
        return 0
    if not shutil.which("claude"):
        print("claude CLI not found on PATH.")
        return 2
    out_dir = BENCH / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    (out_dir / "meta.json").write_text(json.dumps({
        "model": a.model, "repeat": a.repeat, "arms": arms, "tasks": [t["id"] for t in tasks],
        "seed": a.seed, "started": datetime.now().isoformat(timespec="seconds"),
        "plugin_version": json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text()).get("version"),
        "claude_version": subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip(),
    }, indent=1))
    prices = _prices()
    for i, (t, arm, n) in enumerate(plan, 1):
        print(f"[{i}/{len(plan)}] {t['id']} · {arm} · #{n} …", end=" ", flush=True)
        r = one_run(t, arm, a.model, n, out_dir, prices, a.keep)
        cost = r["usage"]["cost"] if r.get("usage") else None
        print(("PASS" if r["passed"] else "FAIL") + (f" · ${cost:.3f}" if cost is not None else "")
              + f" · {r['wall_s']}s" + ("" if r["valid"] else f" · INVALID: {'; '.join(r['problems'])}"))
    print(f"\nResults: {out_dir}\nReport:  python3 {BENCH / 'report.py'} {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
