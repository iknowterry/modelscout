# ModelScout 🔭

**Stop paying frontier-model prices for find-and-replace work.**
**On a subscription? Stop burning your usage limits on it.**

Every AI subscription and API key you own has a lineup of models behind it —
and most people run everything on the biggest one. That's like taking a truck
to buy coffee. Whatever you pay with, the spread is not small:

- **API users** pay in dollars — the price gap between tiers is 5–10×.
- **Subscribers** (Claude Max/Pro, ChatGPT Plus, Gemini Advanced) pay in
  **quota**: every frontier-model request burns your rate limit ~5× faster than
  an economy model doing the same job. Tier-right routing is the difference
  between coding until midnight and hitting the "you've reached your limit"
  wall at 4pm.

| The task | What most people use | What it needed | Price gap |
|---|---|---|---|
| Rename a variable across files | Opus-class ($5/$25 per 1M) | Haiku-class ($1/$5) | **~5×** |
| Summarize a doc | GPT frontier | A mini/flash model | **~10×** |
| Actually-hard debugging | ...the big one. Correctly. | The big one | 1× — and ModelScout will say so |

ModelScout is a skill for your AI coding agent that answers one question
correctly, every time you ask it:

> *"Which model should I use for this?"*

## Why it's different from "just ask the AI"

Ask a chatbot which model to use and it guesses from stale training data —
models you don't have, prices that changed, lineups from last year. ModelScout
doesn't guess:

- 🔍 **It scouts what YOU actually have.** One read-only call per provider
  (Anthropic, OpenAI, Gemini, OpenRouter) lists exactly the models *your* keys
  or subscriptions can access. It will never recommend a model you can't use.
- 💰 **Live pricing, not vibes.** Capabilities, context windows, and per-token
  prices come from the open [models.dev](https://models.dev) catalog — so
  recommendations stay correct as models churn, without updating this repo.
- 🎓 **It teaches you the pattern.** Every recommendation names the task tier
  and the reason — "this is a T1 mechanical edit, no reasoning needed, so Haiku
  at $1/$5 clears it." After a few weeks you'll tier tasks yourself without
  asking. A tool that makes itself unnecessary is a tool you can trust.
- ⏳ **Your rate limits last longer.** For subscribers this is the killer
  benefit: routing mechanical work to light models preserves your frontier-model
  quota for the work that actually needs it — same subscription, more usable
  hours per day, fewer limit walls.
- 🚦 **It knows when NOT to cheap out.** When uncertain, it routes *up* — a
  failed cheap run costs more than the right model the first time.
- 🧭 **Bonus (Claude Code):** it also suggests the right session mode — plan
  mode for architecture, accept-edits for mechanical work — so both your tokens
  *and* your attention go where they matter.

**No API keys needed for subscribers.** Declare what you have once ("Claude
Max + ChatGPT Plus") and ModelScout advises from that — savings framed in what
you actually spend: **tokens and rate-limit headroom**, not dollars.

```
inventory  →  classify  →  recommend
(what you    (what the     (cheapest model that
 have)        task needs)   clears the bar — and why)
```

## What you'll actually see

**You don't have to ask.** Every time you start a new task, ModelScout shows a
small card: what kind of task it is, which model fits it best and why, and
then it **just gets on with it**, handing the work to a subagent running that
model:

> **You:** rename `organizerId` to `ownerId` across the codebase and fix imports
>
> **Claude:** 🔭 *ModelScout · T1 mechanical — rename a field across files*
> *Best fit: Haiku — pattern edits need no deep reasoning · ~1/5 of Opus quota*
> *→ Routing to a Haiku subagent*
> …✓ 43 files updated, verified, imports compile.

It works in both directions. Ask a Haiku session to debug a race condition and
the card says *Best fit: Opus* and routes the work **up** to an Opus subagent.
When your current model already fits, the card is one line, *"Opus fits — doing
it here"*, and the work continues. Your main session stays on its model, ready
for the next hard thing.

### Choose how it behaves: switch, ask, or stay

| Mode | On a mismatch ModelScout… | Set it with |
|---|---|---|
| **auto** (default) | routes the task to a best-fit subagent straight away | `modelscout: auto` |
| **ask** | pops up a choice first (below) | `modelscout: ask` |
| **inform** | shows the card and stays on your current model | `modelscout: inform` |
| **off** | stays silent | `modelscout: off` |

In **ask** mode you get a real popup, and your answer can become the default:

> ┌─ **ModelScout: T1 mechanical task — pattern edits. Who should do it?** ─┐
> │  ▸ Run in a Haiku subagent (Recommended)                               │
> │  ▸ Stay on Opus 5.5                                                    │
> │  ▸ Always use a Haiku subagent for T1 tasks                            │
> │  ▸ Always stay for T1 tasks                                            │
> └────────────────────────────────────────────────────────────────────────┘

**Per-tier defaults** override the mode, for example "auto-route everything,
but always ask me on T3 work":

```text
modelscout: auto
modelscout: T3 ask
```

Typing `modelscout: …` changes the setting instantly. It's handled by the hook,
so it costs no model turn. `modelscout: status` shows your settings,
`modelscout: reset` restores the defaults, and **`/modelscout:prefs`** opens
the same settings as a popup.

**Guardrails.** Routed work is always verified by your main model before it
reports back, and redone if it's weak. Destructive or outward-facing steps
(push, deploy, delete, send) and 1–2 step jobs stay on your main session.
Follow-ups like "yes" or "continue" never trigger a card.

## How to invoke it — prompts that work

**Most of the time you don't.** The card appears on every new task by itself.
For questions *about* models, these phrasings trigger the full advisor:

| You want | Say (any language works) |
|---|---|
| A recommendation for a task | *"Which model should I use to [task]?"* · *"Is Opus overkill for this?"* |
| The budget angle | *"What's the cheapest model that can [task]?"* |
| Help with limits | *"I keep hitting my usage limit"* · *"my quota runs out by 4pm"* |
| See your inventory | *"What models do I have access to?"* · *"Refresh my model inventory"* |
| **Guaranteed trigger** | Start with the name: *"**ModelScout**, which model for this refactor?"* |

## Quickstart

### Claude Code (plugin — richest experience)

```bash
claude plugin marketplace add iknowterry/modelscout
```

```bash
claude plugin install modelscout@modelscout
```

Restart Claude Code. You get the per-task card with auto-routing, the
`/modelscout:prefs` settings popup and the full advisor skill. No settings
edits are needed: the hooks register themselves. To update later, run
`claude plugin marketplace update modelscout`, then
`claude plugin update modelscout@modelscout`.

<details><summary>Manual install (no plugin system)</summary>

```bash
git clone https://github.com/iknowterry/modelscout
cp -r modelscout/skills/modelscout ~/.claude/skills/
cp -r modelscout/core modelscout/hooks modelscout/scripts ~/.claude/skills/modelscout/
```

Then add the per-task hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command",
          "command": "bash \"$HOME/.claude/skills/modelscout/hooks/proactive-check.sh\"" } ] }
    ]
  }
}
```
</details>

### Claude Chat / Cowork (claude.ai)

Advisory-only (chat can't run the discovery script), but the same brain:

1. Download the skill zip:
   **[modelscout-claude-ai.zip](https://github.com/iknowterry/modelscout/releases/latest/download/modelscout-claude-ai.zip)**
2. In claude.ai or the desktop app: **Settings → Skills → Add** → upload the zip.
3. Ask any chat: *"which model should I use for X?"* — it asks once what
   subscriptions/keys you have, then recommends with live pricing.

(Or build the zip yourself: `cd adapters/claude-ai && zip -r modelscout-claude-ai.zip modelscout`)

### Codex CLI / Gemini CLI

Copy `core/` to `~/.modelscout/core/`, then paste the snippet from
[`adapters/codex/AGENTS.md`](adapters/codex/AGENTS.md) or
[`adapters/gemini/GEMINI.md`](adapters/gemini/GEMINI.md) into your context file.

### ChatGPT (Custom GPT)

Follow [`adapters/chatgpt/INSTRUCTIONS.md`](adapters/chatgpt/INSTRUCTIONS.md) —
upload `heuristics.md` as knowledge, paste the instructions. Advisory-only.

### Your own agent / router

**The inventory JSON is the product.** Run the script, read
`~/.claude/model-inventory.json`, route however you like:

```jsonc
{
  "generated_at": "2026-07-09T07:00:00+00:00",
  "declared_subscriptions": ["claude-max"],        // present for no-key users
  "providers": {
    "anthropic": {
      "key_present": true,
      "models": [
        {
          "id": "claude-haiku-4-5",
          "display_name": "Claude Haiku 4.5",
          "cost_per_1m": { "input": 1, "output": 5, "cache_read": 0.1, "cache_write": 1.25 },
          "limit": { "context": 200000, "output": 64000 },
          "reasoning": true, "tool_call": true, "structured_output": true,
          "modalities": { "input": ["text", "image"], "output": ["text"] },
          "enriched": true      // false = key can access it, but no catalog metadata
        }
      ]
    }
  }
}
```

## How it works

Three parts, deliberately separated so every surface shares one brain:

| Part | What it is |
|---|---|
| [`core/discover-models.sh`](core/discover-models.sh) | Builds the inventory from your keys (read-only "list models" calls — costs $0, sends no prompts) + caches the models.dev catalog for 7 days |
| [`core/heuristics.md`](core/heuristics.md) | Host-agnostic brain: task tiers T1–T4, capability vetoes, price-band mapping, honesty rules, subscription fallback |
| `skills/`, `adapters/` | Thin per-host wrappers — tune the heuristics once, every surface improves |

**Do I need API keys?** No. Keys give the most precise inventory (one read-only
listing call, never a prompt, $0). Without keys: inside Claude Code the Claude
lineup is detected automatically, and everything else works via declared
subscriptions in `~/.claude/modelscout-profile.json`.

## The heuristics in 20 seconds

1. Tier the task: **T1** mechanical → **T2** standard coding → **T3** hard
   reasoning → **T4** frontier.
2. Veto by capability: context size, vision/PDF, tool use, structured output,
   latency.
3. Pick the cheapest available model in the tier's price band
   (T1 ≤ $5/1M out · T2 $5–20 · T3+ > $20 with `reasoning`).
4. Honesty: bias **up**-tier when uncertain; never recommend a model that isn't
   in your inventory; always explain the tier so you learn the pattern.

Full rules: [`core/heuristics.md`](core/heuristics.md).

## Roadmap

- [ ] **Savings report** — read session transcripts, show "you saved $X (or Y%
  of your quota) this week by tier-right routing"
- [ ] Azure OpenAI / Bedrock / Vertex key detection
- [ ] `modelscout` CLI wrapper (`npx modelscout` → prints inventory + advice)
- [ ] Optional Action endpoint for the Custom GPT adapter

## License

MIT
