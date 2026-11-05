#!/usr/bin/env bash
# ModelScout — UserPromptSubmit hook shim. Logic lives in proactive_check.py.
# Never block the user's prompt: always exit 0.
python3 "$(dirname "$0")/proactive_check.py" 2>/dev/null
exit 0
