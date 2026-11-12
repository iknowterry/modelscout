<p align="center"><img src="assets/icon.png" width="96" alt="ModelScout logo"></p>

# ModelScout

ModelScout knows which AI models you actually have, picks the right one for each task, and proves what that saved. Light work stops spending frontier-model tokens, so API costs drop and subscription usage limits last longer. It is the same open package across Hermes Agent, Claude Code, Codex, ChatGPT desktop and Gemini CLI. Full docs: [github.com/iknowterry/modelscout](https://github.com/iknowterry/modelscout).

## Install

**Hermes Agent:**

```bash
hermes plugins install modelscout --enable
```

**Claude Code:**

```bash
claude plugin marketplace add iknowterry/modelscout && claude plugin install modelscout@modelscout
```

**Codex / ChatGPT desktop:**

```bash
codex plugin marketplace add iknowterry/modelscout && codex plugin add modelscout@modelscout
```

## What it does in Hermes

For each new, substantial prompt, ModelScout first shows a short card:

> `🔭 ModelScout` **T1 mechanical** · rename a field across 40 files\
> Best fit: `claude-haiku-4.5` — pattern edits need no deep reasoning · ~1/5 of the current model's cost\
> → ⚡ Delegating to a light-model subagent

Then it acts on your default for that tier:
- **switch:** hands the task to `delegate_task`, which needs a `model_map` route for that model, for example from `advanced-delegation`. Routing works up-tier too: a hard task in an economy-model session goes to a stronger model.
- **ask:** shows numbered choices and waits for your answer.
- **stay:** does the work on the current model.

Follow-ups ("yes, test it"), quick questions and chit-chat get no card.

Picks come from the models your own keys and subscriptions reach, priced live from the [models.dev](https://models.dev) catalog. On Hermes that catalog is Hermes's own `models_dev_cache.json`, which Hermes keeps fresh, so new models appear without a plugin update or a manual refresh. It never suggests a model you can't use.

## What the plugin registers

| Surface | What it does |
|---|---|
| `pre_llm_call` hook | Adds the card instructions to new, substantial prompts. Answers `modelscout: …` settings commands itself, blocking the turn so it makes no model call. |
| `subagent_start` hook | Marks delegated children, so a child never gets a card or re-routes the task it was given. |
| `subagent_stop` hook | Records how each ModelScout-routed child ended (tier, model from `state.db`, status). No goal text. |
| `/modelscout` command | `status` (settings and catalog age), `savings`, `weak`, `outcomes`, `forget`, `refresh`, `auto`, `ask`, `inform`, `off`, `reset`, and per-tier defaults such as `T1 stay` or `T3 switch` |
| `modelscout:modelscout` skill | The full recommendation logic: tiers, price bands, honesty rules, savings report |

No tools, no middleware, no Python dependencies.

## Settings

Type `modelscout: <setting>` in a prompt or `/modelscout <setting>`:
- **Modes:** `auto` (route without asking), `ask`, `inform` (card only) and `off`.
- **Per-tier defaults:** for example `T1 switch`, `T3 stay`. A per-tier default beats the mode.
- **Savings:** `savings` prints the measured report. It counts delegated child sessions whose goal starts with `ModelScout:` (the card asks for `ModelScout: <Tier> · <goal>`), using their own token usage, cost-weighted, with every price named.
- **Outcomes:** the `subagent_stop` hook records how each routed child ended: tier, model and status only, in `~/.claude/modelscout-outcomes.jsonl`. `weak` marks the last finished one as a poor result, the only status that counts against a model. Failed and interrupted runs are recorded as neutral errors. `outcomes` lists them.
- **Learning:** when a model's recent results for a tier are weak (at least 3 finished in 30 days, 40% or more weak), that tier is routed one step up until the weak results age out. `forget` clears it.

## Disclosures

- **Files read and written:** settings live in `~/.claude/modelscout-profile.json`, which is shared with ModelScout on the other agents. Routed-child outcomes are appended to `~/.claude/modelscout-outcomes.jsonl` (tier, model, status, time; no goal text). Model lists are read from `~/.claude/model-inventory.json`, `~/.claude/model-catalog.json` and Hermes's own `$HERMES_HOME/models_dev_cache.json` when present (read-only).
- **Savings report:** reads Hermes's session database (`$HERMES_HOME/state.db`, default `~/.hermes/state.db`) and Claude Code transcripts under `~/.claude/projects/`. Both are opened read-only.
- **Network and credentials:** in Hermes the plugin code makes no network calls and never reads credentials; `/modelscout refresh` only reports the age of Hermes's cache. The bundled skill can tell the agent to run `skills/modelscout/scripts/discover-models.sh`, which goes through Hermes's normal terminal-tool approval. That script reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY` and `OPENROUTER_API_KEY` from the environment. It sends each key only to its own provider's read-only "list models" endpoint and fetches the public models.dev catalog. Skip it and ModelScout uses the host's model lineup and the catalog.
- **Other hosts only:** On Claude Code, Codex and Gemini CLI (not Hermes), `hooks/session_start.py` runs `scripts/catalog.py` in a detached process to fetch the public models.dev catalog weekly; no keys or user data are sent, and `modelscout: catalog off` disables it. Hermes does not load that hook.
- **Not present:** no telemetry, no background processes in Hermes, no self-updating, no runtime patches of Hermes.

## License

MIT
