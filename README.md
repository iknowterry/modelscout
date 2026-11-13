<p align="center"><img src="plugins/modelscout/assets/icon.svg" width="112" alt="ModelScout logo"></p>

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

**ModelScout knows which models *you* actually have, picks the right one for
every task, and proves what that saved, across every agent you use.**

It's an open [Agent Skills](https://agentskills.io) plugin. On every task, it
answers the question you'd otherwise guess at:

> *"Which model should I use for this?"*

Then it acts on the answer: it hands the task to a subagent on that model and
checks the result.

**Works in:** Claude Code · Codex · the ChatGPT desktop app · Gemini CLI ·
Hermes Agent · claude.ai · Grok Build *(beta)*. It's one package, installed with each host's own plugin command.

## Why it's different

Model routers exist. Most silently swap the model on every request, from a
fixed list someone configured. ModelScout is built on three things they don't
combine:

- 🔍 **Grounded in what you actually have.** One read-only call per provider
  (Anthropic, OpenAI, Gemini, OpenRouter), or your declared subscriptions,
  defines exactly which models are available to you. Prices and capabilities
  come live from the open [models.dev](https://models.dev) catalog. New models
  show up with no update, and it never recommends a model you can't use.
- 📊 **Proof, not estimates.** `modelscout: savings` measures the *subagents'
  own* token usage from real logs. Routers that only read the main session
  miss exactly the tokens that moved. It's cost-weighted, and it names the
  price behind every number. For subscribers, the % saved is quota freed.
- 🌐 **One brain, every agent.** The same skill, settings and card work in
  Claude Code, Codex, ChatGPT desktop, Gemini CLI, Hermes and claude.ai. Other
  routers each serve a single host.

And on every task:

- 🎓 **It teaches you the pattern.** The card names the tier and the reason:
  "T1 mechanical edit, no reasoning needed, so Haiku clears it." After a few
  weeks you'll tier tasks yourself.
- ⚡ **It acts, then checks.** It starts a subagent on the best-fit model, and
  your main model verifies the result before reporting.
- 🚦 **It knows when NOT to cheap out.** It routes *up* for hard work, and
  when unsure it biases up. A failed cheap run costs more than the right model
  the first time.
- ⏳ **Your rate limits last longer.** Mechanical work on light models leaves
  your frontier-model quota for the work that needs it.
- 🧠 **It learns from weak results.** When a light model keeps doing a poor
  job on one kind of task, ModelScout stops sending that tier to it and routes
  one step up. Errors such as a usage limit or an outage never count.

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
> **Claude:**
>
> > `🔭 ModelScout` **T1 mechanical** · rename a field across files\
> > Best fit: `Haiku` — pattern edits need no deep reasoning · ~1/5 of Opus quota\
> > → ⚡ Routing to a `Haiku` subagent
>
> …✓ 43 files updated, verified, imports compile.

It works in both directions. Ask a Haiku session to debug a race condition and
the card says *Best fit: Opus* and routes the work **up** to an Opus subagent.
When your current model already fits, the card is one line:
> `🔭 ModelScout` **T3 hard reasoning** · `Opus` fits — doing it here

and the work continues. Your main session stays on its model, ready
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

### It learns which models hold up

ModelScout records how each routed subagent ended: the tier, the model and a
status. It stores no task text.

| Status | Means | Counts against the model? |
|---|---|---|
| **ok** | The subagent finished | No |
| **weak** | The result was poor: your main model had to redo it, or you typed `modelscout: weak` | **Yes** |
| **error** | A usage limit, an outage, a denied permission or an interrupt | No |

When a model has at least 3 finished results for a tier in the last 30 days and
40% or more of them were weak, that tier is routed one step up, for example T1
from Haiku to Sonnet. The card instructions say why, and it wears off on its
own after 30 days, so the cheaper model gets another try.

```text
modelscout: weak       # the last routed result was poor
modelscout: outcomes   # results per tier and model, and what was learned
modelscout: forget     # clear what was learned
```

## How much does it save? Measured, not guessed

Type `modelscout: savings` (or ask *"how much has ModelScout saved me?"*).
The calculator reads your Claude Code session logs and Hermes Agent's session
database (read-only) and measures every task ModelScout routed. It reports:
- **Tokens** handled by the lighter model, counted once per API message
- **Percentage saved** versus running the same tokens on your main model.
  It's cost-weighted, so cheap cache reads don't inflate it. For subscribers,
  this is the share of usage-limit quota freed.
- **Main-model budget freed,** in tokens
- **Time:** measured subagent run time. No invented speed-up claims.

Example output (illustrative numbers):

```text
🔭 ModelScout savings — last 30 days
Routed down to lighter models: 12 task(s), 3.1M tokens, 41.0 min of subagent time
  Saved: 76% of what the main model would have used (≈ $4.20 at API prices)
  Main-model budget freed: ≈ 2.4M tokens' worth
```

**A real sample.** The author's machine over 120 days, counting every
lighter-model subagent (`savings.py --days 120 --all`). Routing was done by
hand or by other tools before v0.3.0 added the ModelScout marker.

| Measured over 120 days (n = 68 routed tasks) | Value |
|---|---|
| Tokens handled by lighter models | 47.6M |
| Saved vs. the main model | **76%** ($53 at API prices) |
| Main-model budget freed | ≈ 36.4M tokens |
| Routes | Sonnet→Haiku ×26 · Fable→Sonnet ×28 · Fable→Haiku ×9 · Opus→Haiku ×1 |

Assumes the main model would have used the same number of tokens. Prices come
from the models.dev catalog, falling back to the newest same-family price,
and the report names every price it used. One person's workload is an
example, not a benchmark.

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
git clone https://github.com/iknowterry/modelscout ~/modelscout
cp -r ~/modelscout/plugins/modelscout/skills/modelscout ~/.claude/skills/
```

Then add the per-task hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command",
          "command": "bash \"$HOME/modelscout/plugins/modelscout/hooks/proactive-check.sh\" --host=claude" } ] }
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

### Codex CLI and the ChatGPT desktop app

```bash
codex plugin marketplace add iknowterry/modelscout
```

```bash
codex plugin add modelscout@modelscout
```

Start a new session. The skill gives you the card and the advice right away.
For the per-task hook, run `/hooks` once in Codex and trust ModelScout's hooks;
Codex skips plugin hooks until you do. In Codex, ModelScout tells you the exact
`/model` command to run. It only routes automatically where the host lets it
start a subagent on a chosen model. (Plugins that contain hooks can't be
listed in OpenAI's public plugin directory, so install from this repo.)

### Gemini CLI *(untested: Gemini CLI isn't on the author's machine)*

```bash
gemini skills install https://github.com/iknowterry/modelscout.git --path plugins/modelscout/skills/modelscout
```

That installs the skill. The hook script also understands Gemini's
`BeforeAgent` event if you add it to `~/.gemini/settings.json`.

### Grok Build (xAI) *(beta: built from xAI's docs, not yet tested live)*

Grok Build reads Claude-format plugins, so the same package installs:

```bash
grok plugin marketplace add iknowterry/modelscout
grok plugin install modelscout --trust
```

Then, in a Grok session, type `modelscout: grok setup` and start a new session.

Why the extra step: Grok Build discards the context a prompt hook adds, so the
per-task block can't arrive the way it does in Claude Code. `grok setup` writes
the same instructions once to `~/.grok/rules/modelscout.md` (or
`$GROK_HOME/rules/`), which Grok loads into every session. ModelScout then keeps
that file current at session start and whenever you change a setting, and only
touches it if it wrote it. `modelscout: grok remove` deletes it.

What to expect:
- Routing uses `spawn_subagent`'s `model` argument. If you've turned on Grok's
  *subagent model inheritance*, that argument is hidden and the work stays on
  your current model.
- xAI's own lineup is close in price (grok-4.5 to 4.7 cost the same), so stock
  Grok saves little beyond T1. The bigger savings come from the custom models
  you add under `[model.<name>]` in `~/.grok/config.toml` (Claude, GPT, Gemini…).
  ModelScout prices them from the catalog and routes to them by picker name.
- `modelscout:` commands (status, savings, auto, ask, T1 stay, …) work. Outcome
  tracking and learning don't record Grok subagents yet.

### Hermes Agent (Nous Research)

ModelScout is a native Hermes plugin (since v0.3.7). It's listed in the
[Hermes plugin marketplace](https://hermes-agent.nousresearch.com/marketplace/modelscout).
It registers:
- a `pre_llm_call` hook that shows the card on each new task;
- the `modelscout:modelscout` skill;
- a `/modelscout` command (`status`, `savings`, `auto`, `ask`, `inform`, `off`, `T1 stay`, …).

It passes `hermes plugins validate` and `hermes plugins doctor` on Hermes v0.23.0.

```bash
hermes plugins install modelscout --enable
```

Or install from a clone:

```bash
git clone https://github.com/iknowterry/modelscout ~/modelscout && ln -s ~/modelscout/plugins/modelscout ~/.hermes/plugins/modelscout && hermes plugins enable modelscout
```

Hermes gives subagents a model only through its delegation config. Per-task
auto-routing therefore needs the `advanced-delegation` plugin's `model_map`.
Without it, ModelScout recommends the model and tells you how to switch.

<details><summary>Skill only, or the older shell hook</summary>

- **Skill only:** `hermes skills install iknowterry/modelscout/plugins/modelscout/skills/modelscout`
- **Shell hook:** the plugin replaces it. On older Hermes versions, add this to `~/.hermes/config.yaml`:
  ```yaml
  hooks:
    pre_llm_call:
      - command: "~/modelscout/plugins/modelscout/hooks/proactive-check.sh"
  ```
</details>

### Any other Agent Skills host

Copy `plugins/modelscout/skills/modelscout/` into the host's skills folder.
For example, `~/.agents/skills/` is read by both Codex and Gemini CLI. The
skill is self-contained: heuristics, discovery, settings and savings scripts
are all inside it.

### ChatGPT web (Custom GPT)

Follow [`adapters/chatgpt/INSTRUCTIONS.md`](adapters/chatgpt/INSTRUCTIONS.md):
upload `heuristics.md` as knowledge and paste the instructions. This route is
advisory-only.

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

Everything lives in one portable plugin, [`plugins/modelscout/`](plugins/modelscout), so every host shares one brain:

| Part | What it is |
|---|---|
| [`scripts/discover-models.sh`](plugins/modelscout/skills/modelscout/scripts/discover-models.sh) | Builds the inventory from your keys (read-only "list models" calls — costs $0, sends no prompts) |
| [`scripts/catalog.py`](plugins/modelscout/skills/modelscout/scripts/catalog.py) | Keeps the models.dev catalog fresh on its own (see below), and merges in Hermes's cache when it's there |
| [`references/heuristics.md`](plugins/modelscout/skills/modelscout/references/heuristics.md) | Host-agnostic brain: task tiers T1–T4, capability vetoes, price-band mapping, honesty rules, subscription fallback |
| [`scripts/prefs.py`](plugins/modelscout/skills/modelscout/scripts/prefs.py), [`scripts/savings.py`](plugins/modelscout/skills/modelscout/scripts/savings.py) | Your switch/ask/stay defaults, and the measured savings report |
| [`hooks/`](plugins/modelscout/hooks) | One prompt hook that speaks Claude Code, Codex and Gemini CLI, and shows the per-task card |
| [`scripts/outcomes.py`](plugins/modelscout/skills/modelscout/scripts/outcomes.py) | Records whether each routed subagent got the job done (tier, model, status; no goal text). `modelscout: weak` flags a poor result, and a tier whose model keeps getting flagged is routed one step up |

**Does the catalog stay current?** Yes, with no manual step. On Claude Code,
Codex and Gemini CLI, when the catalog is more than 7 days old, the session-start
hook fetches it in the background: one public GET to `https://models.dev/api.json`,
with no keys and no data about you. On Hermes, ModelScout reads Hermes's own
models.dev cache and makes no network calls. `modelscout: refresh` updates it now,
`modelscout: status` shows its age, and `modelscout: catalog off` turns the
background refresh off.

**Do I need API keys?** No. Keys give the most precise inventory (one read-only
listing call, never a prompt, $0). Without keys: inside Claude Code the Claude
lineup is detected automatically, and everything else works via declared
subscriptions in `~/.claude/modelscout-profile.json`.

## The heuristics in 20 seconds

1. Tier the task: **T1** mechanical → **T2** standard coding → **T3** hard
   reasoning → **T4** frontier.
2. Veto by capability: context size, vision/PDF, tool use, structured output,
   latency.
3. Pick the model in the tier's price band (per 1M output tokens): T1 ≤ $5 ·
   T2 above $5, below $20 · T4 the newest model at $20 or more · T3 the newest
   one priced below T4.
4. Honesty: bias **up**-tier when uncertain; never recommend a model that isn't
   in your inventory; always explain the tier so you learn the pattern.

Full rules: [`heuristics.md`](plugins/modelscout/skills/modelscout/references/heuristics.md).

## Roadmap

Shipped:

- [x] Savings report from real session logs: Claude Code (v0.3.0), Hermes Agent (v0.3.4)
- [x] Native Hermes plugin with hook, skill and `/modelscout` command (v0.3.7). Listed in the Hermes marketplace (v0.3.10)
- [x] Model catalog keeps itself fresh, no manual refresh (v0.3.9)
- [x] Outcome tracking and routing that learns: a model that keeps giving weak results for a tier is skipped for it (v0.3.9)
- [x] Context-tiered prices in the savings report (v0.3.9)
- [x] The main model reports weak results itself, so learning needs no typing (v0.3.10)

Next:

- [x] Grok Build support (beta), through a rules file and `spawn_subagent`'s `model` argument *(unreleased)*
- [x] Azure OpenAI / AWS Bedrock / Google Vertex AI detected from credentials, with no cloud API calls *(unreleased)*
- [ ] Grok Build: live test, plus outcome tracking for `spawn_subagent`
- [ ] Savings net of the main model's briefing and checking, so the figure is no longer an upper bound
- [ ] Codex and Gemini: savings report from their session logs, and outcome tracking
- [ ] Subscription-aware picks: limit Codex/Gemini/Grok picks to the models a declared subscription (e.g. ChatGPT Plus) actually includes

Later (these need hosting or publishing):

- [ ] `npx modelscout` CLI that prints your inventory and advice
- [ ] Optional Action endpoint for the Custom GPT adapter

## License

MIT
