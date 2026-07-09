#!/usr/bin/env bash
# ModelScout proactive mode — UserPromptSubmit hook.
# Injects a standing instruction once per session; after that, Claude tiers
# every request silently and only speaks up when the model is mismatched.
set -uo pipefail

input="$(cat)"
session_id="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id','default'))" 2>/dev/null || echo default)"

state_dir="${TMPDIR:-/tmp}/modelscout"
mkdir -p "$state_dir"
state="${state_dir}/injected-${session_id}"

# Inject only on the first prompt of a session — the instruction persists in context.
[ -f "$state" ] && exit 0
touch "$state"

cat <<'EOF'
<modelscout-proactive>
ModelScout proactive mode is enabled. For each user request that involves real
work (not greetings, quick questions, or mid-task follow-ups), silently
classify its tier per the modelscout skill's heuristics (T1 mechanical, T2
standard, T3 hard reasoning, T4 frontier) and compare against the model you are
currently running as. Then:

- MATCH or unclear → say nothing about models. Just do the work.
- SMALL MISMATCH (one tier) → prepend exactly one line before starting, e.g.:
  "💡 ModelScout: this is a T1 task — `/model haiku` would do it at ~1/5 the
  cost." Then do the work on the current model without waiting.
- LARGE MISMATCH on a substantial task (e.g. T1 bulk work on a frontier model,
  or T3 debugging on an economy model) → use the AskUserQuestion tool ONCE with
  options: (1) "Run in right-sized subagent (Recommended)" — you then delegate
  with the Agent tool's model override; (2) "Continue on current model";
  (3) "Mute ModelScout this session". If the user picks mute, never raise it
  again this session.

Rules: at most one suggestion per task, never repeat a declined suggestion,
never suggest models not in the user's inventory (~/.claude/model-inventory.json;
inside Claude Code the Claude lineup is always available), and when the current
model is the RIGHT choice for a hard task, an occasional "T3 — you're on the
right model" is welcome but keep it rare.
</modelscout-proactive>
EOF
