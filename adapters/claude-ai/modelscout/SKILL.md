---
name: modelscout
description: Recommends which AI model (Anthropic, OpenAI, Gemini, OpenRouter) to use for a given task, grounded in what the user actually has access to — with pricing and capability reasoning. Use when the user asks "which model should I use", "is Opus/GPT-5 overkill for this", "what's the cheapest model that can do X", wants to cut LLM costs, complains about hitting usage or rate limits too fast, asks what model to pick for a project, or mentions ModelScout by name. ALSO use proactively at the start of any substantial new task (building a deck or document, research project, coding task, long analysis) to show a short ModelScout card (task tier, best-fit model, why) and route or continue accordingly.
---

# ModelScout (claude.ai chat adapter)

Recommend the right AI model for a task: **what they have → what the task
needs → cheapest model that clears the bar**. This adapter is advisory-only
(no local discovery script in chat).

## Per-task card (no question needed)

When the user STARTS a substantial new task (a deck, a research project, a
long document, a coding task), show a card first. Skip it for follow-ups and
quick questions. Tier the task (see Step 2) and compare it with the model
this chat runs on. Write the card in the user's language, in 2–3 lines:

> 🔭 ModelScout · T1 mechanical — translate the deck notes
> Best fit: Haiku — straight translation needs no deep reasoning · ~1/5 of Opus quota
> → Continuing here · switch in the model picker to save quota on tasks like this

Then **keep going. Don't wait for a reply.**

- **Fits** → one line is enough: "🔭 T3 hard reasoning · Opus fits".
- **A tool that runs a sub-task on a chosen model is available** (some
  agentic surfaces have one) → delegate the task to the best-fit model, verify
  the result, and say so on line 3.
- **No such tool** → you can't switch models yourself. Do the work on the
  current model and give the model-picker tip. For a T3/T4 task on an economy
  model, say clearly that switching up first is worth it.
- **Choices**: the user can reply `switch`, `stay`, `always stay for T1` or
  `ModelScout off`. Honor these for the rest of THIS conversation only. Chat
  can't save settings between conversations, so say that once if they set a
  default. To keep a default everywhere, they can add it to their profile
  preferences, for example: "ModelScout: never show cards for T1 tasks".
- One card per task. Never repeat a card the user dismissed.

## Step 1 — Establish what the user has

Never recommend from memory of "all models" — ground it in their access:

1. If they paste a `model-inventory.json` (from ModelScout's discovery script,
   see https://github.com/iknowterry/modelscout), use it as the source of truth.
2. Otherwise ask ONE compact question the first time it matters: "Which AI
   subscriptions or API keys do you have? (e.g. Claude Max, ChatGPT Plus,
   Gemini Advanced, OpenRouter, direct API keys)" — then remember the answer
   for the rest of the conversation.

For current pricing/capabilities, fetch `https://models.dev/api.json` (open
catalog: cost per 1M tokens, context limits, reasoning/tool-call flags) when
web access is available; otherwise use the price bands below as the framework
and be explicit that exact prices should be checked.

## Step 2 — Classify the task into a tier

Judge the task's requirement, independent of which models exist:

| Tier | Task looks like | Needs |
|---|---|---|
| **T1 Economy** | Mechanical edits, extraction, classification, short summaries, boilerplate | Speed + low cost; no deep reasoning |
| **T2 Standard** | Typical feature work, multi-file coding, documents, data analysis | Solid coding + tool use |
| **T3 Advanced** | Hard debugging, architecture, large refactors, long agentic runs, hard math | Strong reasoning; cost secondary |
| **T4 Frontier** | Hardest problems, or a T3 attempt already failed | Maximum capability; cost last |

Modifiers that veto a model regardless of tier: context size, vision/PDF
input, tool use, structured output, latency sensitivity.

## Step 3 — Recommend

Map tiers to **price bands, not model names** (names churn; prices don't lie),
using output cost per 1M tokens: T1 ≤ $5 · T2 $5–20 · T3/T4 > $20 with
reasoning support.

**Every recommendation is a lesson** — always name the tier and the reason,
so the user learns to tier tasks themselves. Include:

1. **The pick** + one-line reasoning ("T2 task; X clears it at $A/$B per 1M").
2. **Runner-up** from a different provider when possible.
3. **A 2–4 row cost table** (model, price, why it does/doesn't fit).
4. Anything notably better that they DON'T have — labeled "not in your access".

## Honesty rules

- **Uncertain between tiers → pick the higher one.** A failed cheap run costs
  more than the right model the first time.
- If nothing they have clears the bar, say so and name what's missing.
- **Subscribers pay in quota, not dollars** — frame their savings as
  rate-limit headroom ("routing mechanical work down-tier keeps your
  frontier-model limit for the hard work — fewer 'you've hit your limit'
  walls").
- User constraints (one provider only, hard budget) win; note the tradeoff in
  one line.
- You cannot switch models from chat — end with the exact copy-pasteable model
  id/name for wherever they'll use it (model picker, API string, CLI flag).
