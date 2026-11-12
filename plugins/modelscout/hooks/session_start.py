#!/usr/bin/env python3
"""ModelScout — SessionStart hook (Claude Code, Codex, Gemini CLI).
Announces that ModelScout is active, and keeps the model catalog fresh: when it
is more than 7 days old, a detached background process fetches models.dev
(one public GET, no keys). Always exits 0; prints JSON only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "modelscout" / "scripts"))


def refresh_catalog_in_background():
    """Start a detached `catalog.py refresh` when the catalog is stale. Silent:
    stdout must stay JSON-only, and offline or sandboxed hosts just skip it."""
    import subprocess
    import catalog
    if prefs_off_refresh() or not catalog.needs_refresh():
        return
    catalog.ATTEMPT_STAMP.parent.mkdir(parents=True, exist_ok=True)
    catalog.ATTEMPT_STAMP.touch()  # claim the attempt so parallel sessions don't all fetch
    subprocess.Popen([sys.executable, str(Path(catalog.__file__)), "refresh"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)


def prefs_off_refresh():
    import prefs
    return not prefs.catalog_auto_refresh()


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    import prefs
    try:
        refresh_catalog_in_background()
    except Exception:
        pass
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
    # Announce only in a fresh conversation; after resume/compact it would repeat mid-conversation.
    announce = ""
    if data.get("source") in (None, "startup", "clear"):
        announce = (f"In your FIRST reply that involves real work, prepend one line: "
                    f"\"🔭 ModelScout active ({mode} mode)\". Do not repeat it afterwards. ")
    text = (f"ModelScout is ACTIVE in this session (mode: {mode}; {note}).\n"
            f"{announce}Per-task behavior follows the <modelscout> block injected with each new task prompt.")
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
