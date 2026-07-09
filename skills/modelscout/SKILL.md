---
name: modelscout
description: Recommends which AI model (Anthropic, OpenAI, Gemini, OpenRouter) to use for a given task, grounded in the models the user's API keys can actually access — with live pricing and capability data. Use when the user asks "which model should I use", "is Opus/GPT-5 overkill for this", "what's the cheapest model that can do X", wants to cut LLM costs, asks what models they have access to, or before delegating subtasks to subagents where a cheaper model may suffice.
---

# ModelScout (Claude adapter)

Recommend the right model for a task: **inventory → classify → recommend**.
The full recommendation logic lives in `core/heuristics.md`. Locate the `core/`
directory in this order: (1) `core/` inside this skill's own directory
(standalone install), (2) `${CLAUDE_PLUGIN_ROOT}/core/` or `../../core/`
relative to this file (plugin repo layout). Read `heuristics.md` and follow it.
This file covers only what is Claude-specific.

## Step 1 — Load (or build) the inventory

| File | Contents |
|---|---|
| `~/.claude/model-inventory.json` | Models the user's keys can access, with pricing/limits/capabilities |
| `~/.claude/model-catalog.json` | Full models.dev catalog — context on models the user does NOT have |

Run discovery if the inventory is missing, older than 7 days, or the user asks
to refresh:

```bash
bash <core-dir>/discover-models.sh   # core dir located per the rule above
```

Providers detected via env keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GEMINI_API_KEY`/`GOOGLE_API_KEY`, `OPENROUTER_API_KEY`.

**Claude Code special case:** Anthropic models are always available through the
app's own auth even when `ANTHROPIC_API_KEY` is absent from the inventory —
treat the current Claude lineup (Haiku/Sonnet/Opus tiers) as accessible for the
main loop and subagents.

**No API keys? (subscription users):** keys are only used for a read-only
"list models" call — they are NOT required. If the user has no keys but uses
subscriptions (ChatGPT Plus, Gemini Advanced, …), check
`~/.claude/modelscout-profile.json` for `declared_subscriptions`; if absent,
ask the user once which subscriptions/tools they use, write the profile file,
and re-run discovery. Recommend from the catalog filtered to declared
providers, and frame savings as quota saved rather than dollars (see
`core/heuristics.md` §5).

## Step 2 — Classify and recommend

Apply `core/heuristics.md` §1–4 exactly: tier the task (T1–T4), apply the
modifiers, map tiers to price bands, and produce the pick + runner-up + cost
table, with the honesty rules (bias up-tier when uncertain; never suggest a
model not in the inventory).

## Step 3 — Act on it (Claude-specific)

- **Main conversation**: you cannot switch the model yourself — tell the user
  the exact `/model <name>` command to run.
- **Subagents**: you CAN route directly — pass `model: "haiku" | "sonnet" |
  "opus"` on the Agent tool when delegating. Default: T1 subtasks → haiku,
  T2 → sonnet, T3+ → opus/inherit.
- **OpenAI / Gemini / OpenRouter models**: advisory only from inside Claude —
  give the exact model id from the inventory so it's copy-pasteable into the
  user's other tool (their app code, Codex CLI, Gemini CLI, OpenRouter slug).

## Step 4 — Suggest a permission mode (optional, Claude Code only)

The tier also implies how much supervision the session needs. When the user is
starting a task (not mid-flow), append a one-line mode suggestion:

| Tier / situation | Suggested mode | Why |
|---|---|---|
| T1 mechanical | Accept edits | Changes are low-risk; per-edit review is overhead |
| T2 standard | Default | Normal supervision |
| T3 architecture, ambiguous scope | **Plan mode first** | Align on the approach before burning tokens |
| Long autonomous runs | Auto-accept + checkpoint commits | Review at milestones, not per edit |

Keep it to one line (e.g. "T1 → Haiku is plenty; accept-edits mode makes sense
here"). Skip it entirely when the user only asked a pricing/model question.
