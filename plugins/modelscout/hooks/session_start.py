#!/usr/bin/env python3
"""ModelScout — SessionStart hook (Claude Code, Codex, Gemini CLI).
Announces that ModelScout is active. Always exits 0; prints JSON only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "modelscout" / "scripts"))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    import prefs
    mode = prefs.effective()["mode"]
    if mode == "off":
        return
    note = "no API keys detected — the host's own model lineup is available"
    try:
        inv = json.loads((Path.home() / ".claude" / "model-inventory.json").read_text())
        provs = inv.get("providers") or {}
        if provs:
            n = sum(len(p.get("models", [])) for p in provs.values())
            note = f"inventory: {n} models across {len(provs)} provider(s)"
    except Exception:
        pass
    text = (f"ModelScout is ACTIVE in this session (mode: {mode}; {note}).\n"
            f"In your FIRST reply that involves real work, prepend one line: "
            f"\"🔭 ModelScout active ({mode} mode)\". Do not repeat it afterwards. Per-task "
            f"behavior follows the <modelscout> block injected with each new task prompt.")
    event = data.get("hook_event_name") or "SessionStart"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event,
                                             "additionalContext": f"<modelscout-status>\n{text}\n</modelscout-status>"}},
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
