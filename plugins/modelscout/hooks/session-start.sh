#!/usr/bin/env bash
# ModelScout — SessionStart hook shim. Logic lives in session_start.py. Always exit 0.
python3 "$(dirname "$0")/session_start.py" "$@" 2>/dev/null
exit 0
