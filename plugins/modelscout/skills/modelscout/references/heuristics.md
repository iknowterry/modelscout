# ModelScout — Recommendation Heuristics

Host-agnostic logic for recommending an AI model for a task. Any adapter (Claude
skill, Codex `AGENTS.md`, Gemini CLI, Custom GPT, or your own agent) applies these
rules against the user's inventory (`~/.claude/model-inventory.json`).

The flow is always: **inventory → classify → recommend**. Never recommend a model
from memory alone — ground every recommendation in the inventory.

## 1. Classify the task into a tier

Judge the **task's requirement**, independent of which models exist:

| Tier | Task looks like | Needs |
|---|---|---|
| **T1 Economy** | Rename/format/mechanical edits, extraction, classification, short summaries, boilerplate, simple single-file changes | Speed + low cost; no deep reasoning |
| **T2 Standard** | Typical feature work, multi-file edits with tests, general coding Q&A, documents, data analysis | Solid coding + tool use |
| **T3 Advanced** | Gnarly debugging, architecture/design, large refactors, long-horizon agentic runs, hard math | Strong reasoning; cost secondary |
| **T4 Frontier** | Hardest problems, or a T3 attempt already failed | Maximum capability; cost last |

Then apply **modifiers** that can veto a model regardless of tier:

- **Context size**: estimate input tokens; require `limit.context` comfortably above it.
- **Vision/PDF input**: require `modalities.input` to include `image`/`pdf`.
- **Tool use / agentic**: require `tool_call: true`.
- **Structured output**: require `structured_output: true` (where the field exists).
- **Latency-sensitive** (interactive UX, hooks, autocomplete): bias down one tier.

## 2. Map tiers to models by price band, not by name

Model names churn; prices don't lie. Using `cost_per_1m.output`:

| Tier | Price band (output, USD/1M) | Typical families |
|---|---|---|
| T1 | ≤ $5 | Haiku-class, GPT-mini/nano-class, Gemini Flash-class |
| T2 | $5–20 | Sonnet-class, GPT mainline, Gemini Pro-class |
| T3/T4 | > $20 **and** `reasoning: true` | Opus-class, frontier reasoning models |

Prefer the enriched, current alias of a family over deprecated/dated snapshots.

## 3. Recommendation format

**Every recommendation is a lesson.** Always name the tier AND the reason —
never just the model. The goal is that after a few weeks the user can tier
tasks themselves without asking. "Use Haiku" teaches nothing; "this is a T1
task (mechanical rename, no reasoning needed), so Haiku at $1/$5 clears it"
teaches the pattern.

Always include:

1. **The pick**: cheapest available model that clears the tier + modifiers, with
   one-line reasoning ("this is a T2 task; X clears it at $A in / $B out per 1M").
2. **Runner-up**: next-best alternative — a different provider when possible.
3. **A small cost table** (2–4 rows: model, input/output price, why it does or
   doesn't fit).
4. If a notably better-fitting model exists in the catalog but **not** in the
   user's inventory, mention it explicitly as "not in your inventory" — never
   present it as usable.

## 4. Honesty rules

- **When uncertain between two tiers, pick the higher one.** A cheap model
  failing and needing a redo costs more than routing up front.
- If nothing in the inventory clears the bar, say so plainly and name what's
  missing.
- If the inventory is stale (>7 days) and the recommendation is borderline,
  refresh first (`discover-models.sh`).
- Don't recommend deprecated/legacy snapshots when a current alias of the same
  family is available.
- The recommendation is advice about the *task*, not the *user* — if the user
  states a constraint (must stay on one provider, hard budget cap), the
  constraint wins; note the tradeoff in one line.

## 5. No API keys? Declared subscriptions

API keys are used for exactly one thing: a read-only "list models" call so the
inventory reflects real entitlements. **Most users don't have keys** — they use
subscriptions (Claude Pro/Max, ChatGPT Plus, Gemini Advanced) where the app
picks up their access automatically.

Inventory sources, in order of confidence:

1. **API keys** → exact, live inventory (the script).
2. **Host auth** → e.g. inside Claude Code, the current Claude lineup is always
   available regardless of keys.
3. **Declared subscriptions** → `~/.claude/modelscout-profile.json`:

   ```json
   { "declared_subscriptions": ["claude-max", "chatgpt-plus", "gemini-advanced"] }
   ```

   If neither keys nor a profile exist, ask the user ONCE — "Which AI
   subscriptions or tools do you use?" — write the profile file, and don't ask
   again. Recommend from the models.dev catalog filtered to declared providers.

For subscription users, frame savings as **quota/usage-limit saved, not
dollars** — their marginal cost per request is $0, but cheap-model usage burns
their rate limits far slower.
