---
description: View and change ModelScout's defaults — auto-route, ask, or stay, per task tier
---

# ModelScout preferences

1. Find the prefs script: `${CLAUDE_PLUGIN_ROOT}/scripts/prefs.py`. If that path
   doesn't exist, run `find ~/.claude/plugins -path '*modelscout*/scripts/prefs.py' | head -1`.
   Call it PREFS below.
2. Run `python3 PREFS show` and show the user the result as a short table:
   tier, what it means (T1 mechanical, T2 standard, T3 hard reasoning,
   T4 frontier), and what ModelScout does on a mismatch (switch = route to a
   right-sized subagent, ask = popup, stay = keep the current model).
3. Call AskUserQuestion with two questions:
   - "Default for every task tier?" (header "Mode"): options
     "Auto — route to the best-fit subagent (Recommended)", "Ask me each time",
     "Inform only — show the card, never switch", "Off".
   - "Any tier you want handled differently?" (header "Per tier", multiSelect):
     options "T1 mechanical: always stay", "T3 hard reasoning: always ask",
     "T2 standard: always stay", "No overrides".
4. Apply the answers with `python3 PREFS mode auto|ask|inform|off` and
   `python3 PREFS default T<n> switch|stay|ask|clear`. Free-text answers
   ("Other") map to the same commands. Show the final `show` output in one block.
5. Mention the shortcut: typing `modelscout: ask` (or `auto`, `inform`, `off`,
   `T1 stay`, `status`, `reset`) changes settings instantly without a model turn.

$ARGUMENTS
