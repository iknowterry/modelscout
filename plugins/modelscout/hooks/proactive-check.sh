#!/usr/bin/env bash
# ModelScout — prompt hook shim (Claude Code, Codex, Gemini CLI).
# Logic lives in proactive_check.py. Never blocks the user's prompt: always exit 0.
python3 "$(dirname "$0")/proactive_check.py" "$@" 2>/dev/null
exit 0
