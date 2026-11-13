#!/usr/bin/env python3
"""Validate the benchmark task set. No network, no LLM.

For every task under bench/tasks/:
  1. task.json has the required fields and a prompt that does not leak
     internals (tiers, models, subagents, hidden tests).
  2. fixture + setup  -> the hidden check must FAIL (task not already done).
  3. fixture + setup + solution -> the hidden check AND the visible tests PASS.
Also asserts the fixture's own tests pass and that there are exactly
4 / 5 / 3 tasks in tiers T1 / T2 / T3.

Exit status is non-zero if anything is wrong.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
FIXTURE = BENCH / "fixture"
TASKS = BENCH / "tasks"
EXPECTED_TIERS = {"T1": 4, "T2": 5, "T3": 3}
REQUIRED = {"id": str, "tier": str, "title": str, "prompt": str, "timeout_min": int}
OPTIONAL = {"visible_tests_may_fail_before": bool}
LEAKS = re.compile(
    r"\b(tiers?|models?|subagents?|sub-agents?|modelscout|haiku|sonnet|opus|hidden|benchmarks?|"
    r"T[123])\b",
    re.IGNORECASE,
)
VISIBLE = ["-m", "unittest", "discover", "-s", "tests", "-t", "."]
HIDDEN = ["-m", "unittest", "discover", "-s", "_bench_check", "-t", "."]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "_bench_check")


def run(root: Path, args: list[str]) -> tuple[int, str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("SHOPLIB_TAX_RATE", None)
    proc = subprocess.run(
        [sys.executable, *args], cwd=root, env=env, capture_output=True, text=True, timeout=300
    )
    return proc.returncode, proc.stdout + proc.stderr


def overlay(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=IGNORE)


def install_check(task_dir: Path, project: Path) -> None:
    target = project / "_bench_check"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(task_dir / "check", target, ignore=IGNORE)


def tail(output: str, n: int = 12) -> str:
    return "\n".join("      " + line for line in output.strip().splitlines()[-n:])


def check_metadata(task_dir: Path) -> tuple[dict | None, list[str]]:
    problems: list[str] = []
    path = task_dir / "task.json"
    if not path.is_file():
        return None, ["task.json missing"]
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return None, [f"task.json invalid JSON: {exc}"]
    for key, typ in REQUIRED.items():
        if key not in data:
            problems.append(f"task.json missing {key!r}")
        elif not isinstance(data[key], typ) or isinstance(data[key], bool):
            problems.append(f"task.json {key!r} must be {typ.__name__}")
    for key, typ in OPTIONAL.items():
        if key in data and not isinstance(data[key], typ):
            problems.append(f"task.json {key!r} must be {typ.__name__}")
    extra = set(data) - set(REQUIRED) - set(OPTIONAL)
    if extra:
        problems.append(f"task.json has unknown fields: {sorted(extra)}")
    if data.get("id") != task_dir.name:
        problems.append(f"task.json id {data.get('id')!r} != directory {task_dir.name!r}")
    if data.get("tier") not in EXPECTED_TIERS:
        problems.append(f"bad tier {data.get('tier')!r}")
    if isinstance(data.get("timeout_min"), int) and data["timeout_min"] <= 0:
        problems.append("timeout_min must be positive")
    for key in ("title", "prompt"):
        if isinstance(data.get(key), str) and not data[key].strip():
            problems.append(f"{key} is empty")
    leak = LEAKS.search(data.get("prompt", "") if isinstance(data.get("prompt"), str) else "")
    if leak:
        problems.append(f"prompt mentions {leak.group(0)!r}")
    check = task_dir / "check"
    if not (check / "__init__.py").is_file():
        problems.append("check/__init__.py missing")
    if not list(check.glob("test_*.py")):
        problems.append("check/ has no test_*.py")
    solution = task_dir / "solution"
    if not solution.is_dir() or not any(p.is_file() for p in solution.rglob("*")):
        problems.append("solution/ is missing or empty")
    return data, problems


def validate_task(task_dir: Path, data: dict) -> tuple[list[str], dict]:
    problems: list[str] = []
    row = {"setup": "-", "before": "?", "after": "?", "visible": "?"}
    with tempfile.TemporaryDirectory(prefix="bench-validate-") as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(FIXTURE, project, ignore=IGNORE)
        setup = task_dir / "setup"
        if setup.is_dir():
            overlay(setup, project)
            row["setup"] = "yes"
        may_fail = bool(data.get("visible_tests_may_fail_before"))

        rc, out = run(project, VISIBLE)
        if rc != 0 and not may_fail:
            problems.append("visible tests fail after setup but visible_tests_may_fail_before is not set")
            problems.append(tail(out))
        if rc == 0 and may_fail:
            problems.append("visible_tests_may_fail_before is set but visible tests pass after setup")

        install_check(task_dir, project)
        rc, out = run(project, HIDDEN)
        row["before"] = "fail" if rc != 0 else "PASS"
        if rc == 0:
            problems.append("hidden check already passes before the solution is applied")

        shutil.rmtree(project / "_bench_check")
        overlay(task_dir / "solution", project)
        install_check(task_dir, project)
        rc, out = run(project, HIDDEN)
        row["after"] = "pass" if rc == 0 else "FAIL"
        if rc != 0:
            problems.append("hidden check fails with the reference solution")
            problems.append(tail(out))
        rc, out = run(project, VISIBLE)
        row["visible"] = "pass" if rc == 0 else "FAIL"
        if rc != 0:
            problems.append("visible tests fail with the reference solution")
            problems.append(tail(out))
    return problems, row


def main() -> int:
    problems: list[str] = []
    if not FIXTURE.is_dir():
        print(f"fixture missing: {FIXTURE}")
        return 1
    with tempfile.TemporaryDirectory(prefix="bench-fixture-") as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(FIXTURE, project, ignore=IGNORE)
        rc, out = run(project, VISIBLE)
        if rc != 0:
            problems.append("fixture's own tests fail\n" + tail(out))

    task_dirs = sorted(p for p in TASKS.iterdir() if p.is_dir()) if TASKS.is_dir() else []
    counts = {tier: 0 for tier in EXPECTED_TIERS}
    rows = []
    for task_dir in task_dirs:
        data, meta_problems = check_metadata(task_dir)
        task_problems = list(meta_problems)
        row = {"setup": "-", "before": "-", "after": "-", "visible": "-"}
        if data is not None and not meta_problems:
            counts[data["tier"]] += 1
            started = time.time()
            run_problems, row = validate_task(task_dir, data)
            task_problems += run_problems
            row["secs"] = f"{time.time() - started:.1f}"
        elif data is not None and data.get("tier") in counts:
            counts[data["tier"]] += 1
        rows.append((task_dir.name, data.get("tier", "?") if data else "?", row, task_problems))
        problems += [f"{task_dir.name}: {p}" for p in task_problems]

    for tier, expected in EXPECTED_TIERS.items():
        if counts[tier] != expected:
            problems.append(f"expected {expected} {tier} tasks, found {counts[tier]}")

    width = max([len(r[0]) for r in rows] + [4])
    print(f"{'task':<{width}}  tier  setup  check-before  check-after  visible  secs  status")
    for name, tier, row, task_problems in rows:
        status = "ok" if not task_problems else "PROBLEM"
        print(
            f"{name:<{width}}  {tier:<4}  {row['setup']:<5}  {row['before']:<12}  "
            f"{row['after']:<11}  {row['visible']:<7}  {row.get('secs', '-'):>4}  {status}"
        )
    print(f"\ntiers: " + ", ".join(f"{t}={counts[t]}/{n}" for t, n in EXPECTED_TIERS.items()))
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"\nAll {len(rows)} tasks valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
