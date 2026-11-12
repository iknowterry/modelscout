"""ModelScout for Hermes Agent: native plugin entry point.

Registers:
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
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
_CMD = re.compile(r"^\s*modelscout\s*:\s*(.*)$", re.I | re.S)
_core = None


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


def _on_pre_llm_call(user_message="", model="", **kwargs):
    try:
        prompt = (user_message or "").strip()
        if not prompt:
            return None
        core = _check()
        cmd = _CMD.match(prompt)
        if cmd:
            # Settings commands are answered here; the turn never reaches the model.
            return {"action": "block", "message": core.handle_command(cmd.group(1))}
        eff = core.prefs.effective()
        if eff["mode"] == "off" or core.is_trivial(prompt):
            return None
        return {"context": core.build_block(prompt, None, eff, "hermes", model or None)}
    except Exception:  # noqa: BLE001 - never break the user's turn
        logger.debug("modelscout pre_llm_call failed", exc_info=True)
        return None


def _on_command(raw_args=""):
    try:
        return _check().handle_command(raw_args or "status")
    except Exception as e:  # noqa: BLE001
        return f"ModelScout: {e}"


def register(ctx):
    skill_md = ROOT / "skills" / "modelscout" / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill("modelscout", skill_md)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_command(
        "modelscout",
        handler=_on_command,
        description="ModelScout: status | savings | auto | ask | inform | off | T1 stay",
    )
