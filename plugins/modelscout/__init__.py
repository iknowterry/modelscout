"""ModelScout for Hermes Agent: native plugin entry point.

Registers:
- a `subagent_start` hook that marks delegated children, so a child never gets
  a card or re-routes the task it was given;
- a `subagent_stop` hook that records whether each ModelScout-routed child
  completed (tier, model, status; no goal text) in the shared outcomes log;
- a `pre_llm_call` hook that adds the ModelScout card instructions to each new,
  substantial prompt, and answers `modelscout: ...` settings commands without a
  model call;
- the `modelscout` skill (loaded as `modelscout:modelscout`);
- a `/modelscout` slash command (status, savings, mode and per-tier defaults).

The logic is shared with the Claude Code, Codex and Gemini CLI hooks in
`hooks/proactive_check.py`. Every callback catches its own errors, so a failure
never blocks or breaks a turn.
"""
import importlib.util
import logging
import os
import sqlite3
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
_core = None
_children = {}  # child session id -> routed tier (or None); insertion-ordered, bounded
_MAX_CHILDREN = 512


def _check():
    """Load the shared hook logic once, under a private module name."""
    global _core
    if _core is None:
        name = "modelscout_proactive_check"
        spec = importlib.util.spec_from_file_location(name, ROOT / "hooks" / "proactive_check.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        _core = mod
    return _core


def _on_subagent_start(child_session_id=None, child_goal=None, **kwargs):
    """Remember delegated children so they don't get a card and re-route the
    task they were just given. For a ModelScout-routed goal ("ModelScout: T1 · …")
    also keep its tier, for the outcome recorded at subagent_stop."""
    if not child_session_id:
        return
    tier = None
    try:
        out = _check().outcomes
        if out.is_routed(child_goal):
            tier = out.tier_from(child_goal) or _check().guess_tier(child_goal or "")[0]
    except Exception:  # noqa: BLE001
        logger.debug("modelscout subagent_start failed", exc_info=True)
    _children[child_session_id] = tier
    while len(_children) > _MAX_CHILDREN:
        _children.pop(next(iter(_children)))


def _child_model(child_session_id):
    """The child's model from Hermes's session database, opened read-only."""
    db = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "state.db"
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
        try:
            row = con.execute("select model from sessions where id = ?", (child_session_id,)).fetchone()
        finally:
            con.close()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


def _on_subagent_stop(child_session_id=None, child_status=None, **kwargs):
    """Record whether a ModelScout-routed child got the job done."""
    try:
        tier = _children.get(child_session_id)
        if not tier:
            return
        status = (child_status or "").lower()
        _check().outcomes.record("hermes", tier, _child_model(child_session_id),
                                 "ok" if status == "completed" else "fail", why=status)
    except Exception:  # noqa: BLE001 - never break the parent's turn
        logger.debug("modelscout subagent_stop failed", exc_info=True)


def _on_pre_llm_call(user_message="", model="", session_id="", **kwargs):
    try:
        prompt = (user_message or "").strip()
        if not prompt or (session_id and session_id in _children):
            return None
        core = _check()
        cmd = core.parse_command(prompt)
        if cmd is not None:
            # A recognised settings command is answered here and never reaches
            # the model. Other "ModelScout: …" text (delegated goals) runs as usual.
            return {"action": "block", "message": core.handle_command(cmd, "hermes")}
        eff = core.prefs.effective()
        if eff["mode"] == "off" or core.is_trivial(prompt):
            return None
        return {"context": core.build_block(prompt, None, eff, "hermes", model or None)}
    except Exception:  # noqa: BLE001 - never break the user's turn
        logger.debug("modelscout pre_llm_call failed", exc_info=True)
        return None


def _on_command(raw_args=""):
    try:
        return _check().handle_command(raw_args or "status", "hermes")
    except Exception as e:  # noqa: BLE001
        return f"ModelScout: {e}"


def register(ctx):
    skill_md = ROOT / "skills" / "modelscout" / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill("modelscout", skill_md)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("subagent_start", _on_subagent_start)
    ctx.register_hook("subagent_stop", _on_subagent_stop)
    ctx.register_command(
        "modelscout",
        handler=_on_command,
        description="ModelScout: status | savings | refresh | auto | ask | inform | off | T1 stay",
    )
