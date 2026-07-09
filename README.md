# ModelScout 🔭

**Stop paying frontier-model prices for find-and-replace work.**

Every AI subscription and API key you own has a lineup of models behind it —
and most people run everything on the biggest one. That's like taking a truck
to buy coffee. The price spread is not small:

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
- 🚦 **It knows when NOT to cheap out.** When uncertain, it routes *up* — a
  failed cheap run costs more than the right model the first time.
- 🧭 **Bonus (Claude Code):** it also suggests the right session mode — plan
  mode for architecture, accept-edits for mechanical work — so both your tokens
  *and* your attention go where they matter.

**On a subscription instead of API keys? Even better.** No key needed — declare
what you have once ("Claude Max + ChatGPT Plus") and ModelScout advises from
that. Cheap-model routing doesn't save you dollars there; it saves your **usage
quota** — fewer "you've hit your limit" walls at 4pm.

```
inventory  →  classify  →  recommend
(what you    (what the     (cheapest model that
 have)        task needs)   clears the bar — and why)
```

## What you'll actually see

**You don't have to ask.** With proactive mode on, ModelScout watches every
task and only speaks when something's off:

> **You:** rename `organizerId` to `ownerId` across the codebase and fix imports
>
> **Claude:** 💡 *ModelScout: this is a T1 mechanical task — `/model haiku`
> would do it at ~1/5 the cost.*
> Renaming now… ✻
>
> — and for a big mismatch you get an actual popup:
>
> ┌─ **This is bulk T1 work but you're on Opus ($25/1M out). Route it?** ─┐
> │  ▸ Run in a Haiku subagent (Recommended) — ~5× cheaper               │
> │  ▸ Continue on Opus                                                  │
> │  ▸ Mute ModelScout this session                                      │
> └──────────────────────────────────────────────────────────────────────┘

Pick option 1 and the task runs on the cheap model **automatically** — no
settings, no `/model`, you stay on your main model for the next hard thing.
When the model already fits the task, ModelScout says nothing at all. And it
works in both directions — try to debug a race condition on a cheap model and
it will tell you to route *up*.

## Quickstart

### Claude Code (plugin — richest experience)

```bash
git clone https://github.com/iknowterry/modelscout
cp -r modelscout/skills/modelscout ~/.claude/skills/
cp -r modelscout/core modelscout/hooks ~/.claude/skills/modelscout/
```

That enables ask-mode: *"which model should I use for this refactor?"* — plus
automatic subagent routing (T1 subtasks → Haiku, T3 → Opus).

**Proactive mode** (suggestions appear without asking — see "What you'll
actually see" above) needs one hook in `~/.claude/settings.json`:

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

(Installed as a plugin from a marketplace, the hook in `hooks/hooks.json` is
picked up automatically — no settings edit needed.)

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
