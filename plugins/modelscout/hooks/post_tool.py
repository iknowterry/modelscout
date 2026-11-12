#!/usr/bin/env python3
"""ModelScout — outcome hook for ModelScout-routed subagents (Claude Code).

Events (one script; it branches on hook_event_name):
- PostToolUse on Agent|Task
    async launch ("async_launched", with or without run_in_background)
        → a `pending` outcome keyed by the agent id
    foreground completion ("completed") → `ok`
- PostToolUseFailure on Agent|Task → `error` with a coarse reason bucket
  (limit / unavailable / denied / interrupt / other). Never a quality verdict.
- SubagentStop → resolves a `pending` outcome with that agent id to `ok`, or to
  `error` when the subagent transcript ends on an API error record (usage limit,
  outage). Unknown agent ids are ignored: they were not routed by ModelScout.
Only description-tagged ("ModelScout: T1 · …") agents are recorded, and never a
subagent's own tool calls. Stores tier, model, status and reason only — no goal,
prompt, output, error text or transcript path. Prints nothing; always exits 0.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "modelscout" / "scripts"
ASYNC = ("async_launched", "launched", "running", "backgrounded")
TAIL = 65536


def _outcomes():
    spec = importlib.util.spec_from_file_location("modelscout_outcomes", SCRIPTS / "outcomes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _concrete(model):
    """A full model id ("claude-haiku-4-5"), not an alias ("haiku") or nothing."""
    return bool(model) and "-" in str(model)


def transcript_tail(path, out=None):
    """(model, api_error) from the end of a subagent transcript: the model of
    the last real assistant record, and — when the very last assistant record
    is an API error — a reason bucket. (None, None) when unreadable."""
    model = err = None
    try:
        p = Path(str(path)).expanduser()
        if not p.is_file():
            return None, None
        with open(p, "rb") as f:
            size = f.seek(0, os.SEEK_END)
            f.seek(max(0, size - TAIL))
            lines = f.read().decode("utf-8", "replace").splitlines()
        if size > TAIL and lines:
            lines = lines[1:]  # first line is likely partial
        seen_last = False
        for ln in reversed(lines):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(r, dict) or r.get("type") != "assistant":
                continue
            msg = r.get("message") if isinstance(r.get("message"), dict) else {}
            if not seen_last:
                seen_last = True
                if r.get("isApiErrorMessage"):
                    err = _reason_of(r, msg, out or _outcomes())
            m = msg.get("model")
            if m and m != "<synthetic>":
                model = m
                break
    except Exception:  # noqa: BLE001
        return model, err
    return model, err


def _reason_of(rec, msg, out):
    """Bucket for an API-error record: its `error`/`apiErrorStatus` fields,
    else its text (read here, never stored)."""
    from_fields = out.reason(rec.get("error"), rec.get("apiErrorStatus"))
    if from_fields != "other":
        return from_fields
    text = " ".join(str(c.get("text", "")) for c in (msg.get("content") or []) if isinstance(c, dict))
    return out.reason(text)


def _subagent_stop(data, out):
    aid = data.get("agent_id")
    if not aid:
        return None
    try:
        if str(aid) not in out.OUTCOMES.read_text():  # cheap: most stops aren't ours
            return None
    except OSError:
        return None
    cur = out.find(str(aid))
    if not cur or cur["status"] != "pending":
        return None
    model, err = transcript_tail(data.get("agent_transcript_path"), out)
    if err is None and model is None:  # no transcript: fall back to a short API-error message
        last = str(data.get("last_assistant_message") or "")
        if len(last) < 300 and (last.startswith("API Error") or "hit your" in last):
            err = out.reason(last)
    new_model = model if (model and not _concrete(cur.get("model"))) else None
    return out.resolve(cur["id"], "error" if err else "ok", model=new_model, why=err or "")


def handle(data):
    if not isinstance(data, dict):
        return None
    event = data.get("hook_event_name")
    out = _outcomes()
    if event == "SubagentStop":  # before the agent_id guard: stop payloads carry it
        return _subagent_stop(data, out)
    if data.get("tool_name") not in ("Agent", "Task"):
        return None
    if data.get("agent_id"):  # a subagent's own tool call, not the parent's routing
        return None
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    desc = ti.get("description") or ""
    if not out.is_routed(desc):
        return None
    tier = out.tier_from(desc)
    if event == "PostToolUseFailure":
        why = "interrupt" if data.get("is_interrupt") else out.reason(data.get("error"))
        return out.record("claude", tier, ti.get("model"), "error", why=why)
    tr = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    status = str(tr.get("status") or "").lower()
    aid = tr.get("agentId") or tr.get("agent_id")
    aid = str(aid) if aid else None
    model = tr.get("resolvedModel") or ti.get("model")
    if aid and out.find(aid):  # this agent is already recorded
        return None
    if tr.get("isAsync") or status in ASYNC:
        if not aid:
            return None  # nothing to resolve it by later
        return out.record("claude", tier, model, "pending", id=aid)
    if status in out.FAIL_STATUSES:
        return out.record("claude", tier, model, "error", why=out.reason(status))
    return out.record("claude", tier, model, "ok", id=aid)


def main():
    try:
        handle(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never break the turn
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
