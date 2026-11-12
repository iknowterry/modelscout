#!/usr/bin/env bash
# ModelScout — Agent-tool outcome hook shim (Claude Code). Logic lives in post_tool.py. Always exit 0.
python3 "$(dirname "$0")/post_tool.py" "$@" >/dev/null 2>&1
exit 0
