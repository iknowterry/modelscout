#!/usr/bin/env python3
"""ModelScout — PostToolUse / PostToolUseFailure hook on the Agent tool (Claude Code).

Records whether a ModelScout-routed subagent (description "ModelScout: T1 · …")
completed: tier, model and status in ~/.claude/modelscout-outcomes.jsonl. No goal
text, prompt or output is stored. Background launches are skipped (they have
no result yet). Prints nothing; always exits 0.
"""
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "modelscout" / "scripts"


def _outcomes():
    spec = importlib.util.spec_from_file_location("modelscout_outcomes", SCRIPTS / "outcomes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def handle(data):
    if not isinstance(data, dict) or data.get("tool_name") not in ("Agent", "Task"):
        return None
    if data.get("agent_id"):  # a subagent's own tool call, not the parent's routing
        return None
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    out = _outcomes()
    desc = ti.get("description") or ""
    if not out.is_routed(desc):
        return None
    if ti.get("run_in_background"):
        return None
    tier = out.tier_from(desc)
    if data.get("hook_event_name") == "PostToolUseFailure":
        if data.get("is_interrupt"):
            return None  # the user stopped it; not a verdict on the model
        return out.record("claude", tier, ti.get("model"), "fail", why="error")
    tr = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    status = str(tr.get("status") or "").lower()
    if status in ("async_launched", "launched", "running", "backgrounded"):
        return None
    model = tr.get("resolvedModel") or ti.get("model")
    failed = status in out.FAIL_STATUSES
    return out.record("claude", tier, model, "fail" if failed else "ok", why=status)


def main():
    try:
        handle(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never break the turn
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
