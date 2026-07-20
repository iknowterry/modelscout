#!/usr/bin/env bash
# ModelScout proactive mode — UserPromptSubmit hook.
# Injects a standing instruction (suggest-mode or auto-mode, per the user's
# profile) once per session, re-injecting if the mode/receipts settings change.
set -uo pipefail

input="$(cat)"
session_id="$(printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id','default'))" 2>/dev/null || echo default)"

profile="${HOME}/.claude/modelscout-profile.json"
mode="suggest"
receipts="always"
if [ -s "$profile" ]; then
  read -r mode receipts <<< "$(python3 -c "
import json
d = json.load(open('${profile}'))
print(d.get('mode', 'suggest'), d.get('receipts', 'always'))" 2>/dev/null || echo 'suggest always')"
fi
[ "$mode" = "auto" ] || mode="suggest"
[ "$receipts" = "mismatch-only" ] || receipts="always"

state_dir="${TMPDIR:-/tmp}/modelscout"
mkdir -p "$state_dir"
state="${state_dir}/injected-${session_id}"

# Skip if this session already has the instruction for the current settings.
if [ -f "$state" ] && [ "$(cat "$state" 2>/dev/null)" = "${mode}:${receipts}" ]; then
  exit 0
fi
printf '%s' "${mode}:${receipts}" > "$state"

if [ "$receipts" = "always" ]; then
  RECEIPT_RULE='RECEIPTS ARE ALWAYS ON: even when the current model FITS the
task, prepend a minimal receipt before starting — "🔭 T2 — model fits" (tier +
two or three words, nothing more). The user should see ModelScout thinking on
every real task. Say "modelscout: quiet receipts" to reduce this to
mismatch-only.'
else
  RECEIPT_RULE='Receipts are mismatch-only: when the model fits the task, say
nothing about models at all.'
fi

if [ "$mode" = "auto" ]; then
cat <<EOF
<modelscout-proactive mode="auto">
ModelScout AUTO mode is enabled. This is MANDATORY, not optional: for EVERY
user request that involves real work (not greetings, quick questions, or
mid-task follow-ups), you MUST classify its tier per the modelscout skill's
heuristics (T1 mechanical, T2 standard, T3 hard reasoning, T4 frontier) before
starting, then act:

- CLEAR T1 (and clearly self-contained T2) tasks that do not depend on deep
  session context and are not destructive → delegate to a subagent with the
  right-sized model via the Agent tool's model override (T1 → haiku, T2 →
  sonnet) WITHOUT asking. Prepend the receipt:
  "⚡ ModelScout: auto-routed to Haiku (T1 — mechanical edit)". Give the
  subagent a fully self-contained prompt, and verify its result before
  reporting.
- T3/T4, context-heavy, ambiguous, or destructive tasks → do them yourself on
  the current model. If the current model is clearly UNDER-powered (e.g. an
  economy model on hard debugging), say so in one line and suggest
  \`/model <bigger>\` — never route hard work DOWN.
- Uncertain tier → don't route; do the work on the current model.

${RECEIPT_RULE}

If a routed result is wrong or low-quality, redo it yourself on the current
model without being asked. If the user says "modelscout: suggest mode" (or asks
to stop auto-routing), set "mode": "suggest" in
~/.claude/modelscout-profile.json (preserve other fields) and stop immediately;
"modelscout: quiet receipts" sets "receipts": "mismatch-only" the same way.
Never route to models not in the user's inventory
(~/.claude/model-inventory.json; inside Claude Code the Claude lineup is always
available).
</modelscout-proactive>
EOF
else
cat <<EOF
<modelscout-proactive mode="suggest">
ModelScout proactive mode is enabled. This is MANDATORY, not optional: for
EVERY user request that involves real work (not greetings, quick questions, or
mid-task follow-ups), you MUST classify its tier per the modelscout skill's
heuristics (T1 mechanical, T2 standard, T3 hard reasoning, T4 frontier) and
compare against the model you are currently running as. Then:

- SMALL MISMATCH (one tier) → prepend exactly one line before starting, e.g.:
  "💡 ModelScout: this is a T1 task — \`/model haiku\` would do it at ~1/5 the
  cost." Then do the work on the current model without waiting.
- LARGE MISMATCH on a substantial task (e.g. T1 bulk work on a frontier model,
  or T3 debugging on an economy model) → use the AskUserQuestion tool ONCE with
  options: (1) "Run in right-sized subagent (Recommended)" — you then delegate
  with the Agent tool's model override; (2) "Continue on current model";
  (3) "Always auto-route tasks like this" — merge {"mode": "auto"} into
  ~/.claude/modelscout-profile.json (preserve other fields), confirm in one
  line, and from now on behave per AUTO mode; (4) "Mute ModelScout this
  session". If the user picks mute, never raise it again this session.

${RECEIPT_RULE}

Rules: at most one suggestion per task, never repeat a declined suggestion,
and never suggest models not in the user's inventory
(~/.claude/model-inventory.json; inside Claude Code the Claude lineup is
always available).
</modelscout-proactive>
EOF
fi
