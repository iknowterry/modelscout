---
name: modelscout
description: Picks the right AI model for each task (Claude, OpenAI/ChatGPT, Gemini, OpenRouter), grounded in the models the user's keys or subscriptions can actually access, with live pricing. Shows a short card per task (tier, best-fit model, why), then routes the work to that model or subagent, asks, or stays, per the user's defaults. Use when the user asks "which model should I use", "is this model overkill", "what's the cheapest model that can do X", wants to cut LLM cost or save usage-limit quota, asks what models they have, asks how much ModelScout saved, mentions ModelScout by name, or before delegating subtasks to subagents where a lighter model may suffice.
license: MIT
compatibility: Works in any Agent Skills host (Claude Code, Codex, ChatGPT, Gemini CLI, claude.ai). Scripts need python3 and bash; auto-routing needs a host that can start subagents on a chosen model.
metadata:
  author: iKnowTerry
  version: "0.3.0"
  homepage: https://github.com/iknowterry/modelscout
---

# ModelScout

Recommend the right model for a task: **inventory → classify → recommend → act**.
The full recommendation logic is in [references/heuristics.md](references/heuristics.md).
Read it and follow it. This file covers how to apply it on whatever host you
are running in. Paths below are relative to this skill's folder.

## Step 1: Know what the user has

| File | Contents |
|---|---|
| `~/.claude/model-inventory.json` | Models the user's API keys can access, with pricing, limits and capabilities |
| `~/.claude/model-catalog.json` | The full models.dev catalog, including models the user does NOT have |

- **You can run scripts:** if the inventory is missing, older than 7 days, or
  the user asks for a refresh, run `bash scripts/discover-models.sh`. It reads
  `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY` and
  `OPENROUTER_API_KEY`, and makes only read-only "list models" calls.
- **You can't run scripts (chat apps):** ask once, the first time it matters,
  which subscriptions or keys the user has. Remember the answer for the rest of
  the conversation.
- **The host's own lineup is always available.** That's Claude models inside
  Claude Code and claude.ai, OpenAI models inside Codex and ChatGPT, and Gemini
  models inside Gemini CLI, even when no API key shows up in the inventory.
- **Subscription users with no API keys:** check
  `~/.claude/modelscout-profile.json` for `declared_subscriptions`. Recommend
  from the catalog filtered to those providers, and frame savings as quota
  freed rather than dollars (heuristics §5).

## Step 2: Classify and recommend

Apply heuristics §1–4 exactly: tier the task (T1 mechanical, T2 standard,
T3 hard reasoning, T4 frontier), apply the modifiers, map tiers to price bands,
and follow the honesty rules. Bias up-tier when unsure, and never suggest a
model the user can't use. Every recommendation is a lesson: always name the
tier and the reason.

## Step 3: Show the card, then act

At the start of each new substantial task, show this card in the user's
language, then act on it. Skip it for follow-ups ("yes", "continue") and
quick questions.

```text
🔭 ModelScout · T1 mechanical — rename a field across 40 files
   Best fit: Haiku — pattern edits need no deep reasoning · ~1/5 of Opus quota
   → Routing to a Haiku subagent
```

The default action on a mismatch comes from the user's settings: a per-tier
default wins over the mode, and the mode is the fallback. `auto` means switch,
`ask` means ask, `inform` means stay. Read the settings with
`python3 scripts/prefs.py show`, or use the `<modelscout>` block a hook
injected. Then act according to what the host can do:

| Host capability | switch | ask | stay |
|---|---|---|---|
| Subagents with a model choice (Claude Code Agent tool `model: haiku\|sonnet\|opus`) | Delegate now. Start the Agent `description` with `ModelScout:` and write a self-contained brief. Verify the result before reporting. | Popup (AskUserQuestion): run in subagent / stay / always subagent for this tier / always stay | Do it here |
| Can only advise (Codex, Gemini CLI, chat apps) | Give the exact switch command or model-picker step and continue on the current model | Numbered choices in text, then wait for the answer | Do it here |

- Routing works up-tier as well as down: a T3 task in an economy-model session
  goes to a stronger model.
- Keep these on the main model: destructive or outward-facing steps (push,
  deploy, delete, send), 1–2 step jobs, and work that needs the user's answers
  mid-way.
- **Saving "always" choices:** run `python3 scripts/prefs.py default T1 switch|stay`.
  Chat apps can't save, so honor the choice for the rest of the conversation
  only and say so.

## Step 4: Savings report (hosts that can run scripts)

When the user asks how much ModelScout saved, run `python3 scripts/savings.py`
(add `--days 7` to change the window, `--markdown` for a table). It reads
Claude Code transcripts and measures every subagent whose description starts
with `ModelScout:`:
- tokens handled by the lighter model, deduplicated per API message
- the cost-weighted percentage saved versus the main model, which for
  subscribers is the share of usage-limit quota freed
- measured run time

Always show the report's own assumption line. `--all` counts every lighter
subagent, including ones ModelScout didn't route.

## Step 5: Suggest a permission mode (Claude Code, optional)

| Tier / situation | Suggested mode |
|---|---|
| T1 mechanical | Accept edits |
| T2 standard | Default |
| T3 architecture, ambiguous scope | Plan mode first |
| Long autonomous runs | Auto-accept with checkpoint commits |

One line at most. Skip it for pure pricing or model questions.

## Settings

- **Plugin hosts with hooks:** the user types `modelscout: auto | ask | inform | off | status | savings | reset | T1 stay`.
  The hook saves it instantly, with no model turn.
- **Claude Code:** `/modelscout:prefs` opens the same settings as a popup.
- **Anywhere scripts run:** `python3 scripts/prefs.py mode|default|receipts|reset|show`.
