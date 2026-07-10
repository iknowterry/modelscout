---
name: modelscout
description: Recommends which AI model (Anthropic, OpenAI, Gemini, OpenRouter) to use for a given task, grounded in what the user actually has access to — with pricing and capability reasoning. Use when the user asks "which model should I use", "is Opus/GPT-5 overkill for this", "what's the cheapest model that can do X", wants to cut LLM costs, complains about hitting usage or rate limits too fast, or asks what model to pick for a project. ALSO use proactively at the start of any substantial new task (building a deck or document, research project, coding task, long analysis) to silently check whether the current model fits the task's tier — speak up only on a mismatch.
---

# ModelScout (claude.ai chat adapter)

Recommend the right AI model for a task: **what they have → what the task
needs → cheapest model that clears the bar**. This adapter is advisory-only
(no local discovery script in chat).

## Proactive check (no question needed)

When the user STARTS a substantial new task (a deck, a research project, a
long document, a coding task) — not on follow-ups or quick questions —
silently tier the task (see Step 2) and compare against the model this chat
is running on:

- **Model fits the tier → say nothing about models.** Just do the task.
- **Mismatch → prepend exactly ONE line** before starting, then do the work
  without waiting, e.g.:
  - "💡 ModelScout: งานนี้เป็น T1/T2 — สลับเป็น Haiku ใน model picker จะประหยัดโควต้ากว่า ~5 เท่า"
  - "💡 ModelScout: this is T3 reasoning work — worth switching to Opus in
    the model picker before we go deep."
- Match the user's language. At most one nudge per task; never repeat after
  the user declines or ignores it; if the user says to stop suggesting, stay
  silent for the rest of the conversation.
- You cannot switch the model yourself — the user changes it in the model
  picker (their reply continues on whichever model they choose).

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
