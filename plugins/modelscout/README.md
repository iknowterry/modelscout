<p align="center"><img src="assets/icon.png" width="96" alt="ModelScout logo"></p>

# ModelScout

ModelScout knows which AI models you actually have, picks the right one for each task, and proves what that saved. It is the same open package across Hermes Agent, Claude Code, Codex, ChatGPT desktop and Gemini CLI. Full docs: [github.com/iknowterry/modelscout](https://github.com/iknowterry/modelscout).

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

Picks come from the models your own keys and subscriptions reach, priced live from the [models.dev](https://models.dev) catalog. New models appear without a plugin update, and it never suggests a model you can't use.

## What the plugin registers

| Surface | What it does |
|---|---|
| `pre_llm_call` hook | Adds the card instructions to new, substantial prompts. Answers `modelscout: …` settings commands itself, blocking the turn so it makes no model call. |
| `subagent_start` hook | Marks delegated children, so a child never gets a card or re-routes the task it was given. |
| `/modelscout` command | `status`, `savings`, `auto`, `ask`, `inform`, `off`, `reset`, and per-tier defaults such as `T1 stay` or `T3 switch` |
| `modelscout:modelscout` skill | The full recommendation logic: tiers, price bands, honesty rules, savings report |

No tools, no middleware, no Python dependencies.

## Settings

Type `modelscout: <setting>` in a prompt or `/modelscout <setting>`:
- **Modes:** `auto` (route without asking), `ask`, `inform` (card only) and `off`.
- **Per-tier defaults:** for example `T1 switch`, `T3 stay`. A per-tier default beats the mode.
- **Savings:** `savings` prints the measured report. It counts delegated child sessions whose goal starts with `ModelScout:`, using their own token usage, cost-weighted, with every price named.

## Disclosures

- **Files read and written:** settings live in `~/.claude/modelscout-profile.json`, which is shared with ModelScout on the other agents. Model lists are read from `~/.claude/model-inventory.json` and `~/.claude/model-catalog.json` when present.
- **Savings report:** reads Hermes's session database (`$HERMES_HOME/state.db`, default `~/.hermes/state.db`) and Claude Code transcripts under `~/.claude/projects/`. Both are opened read-only.
- **Network and credentials:** the plugin code makes no network calls and never reads credentials. The bundled skill can tell the agent to run `skills/modelscout/scripts/discover-models.sh`, which goes through Hermes's normal terminal-tool approval. That script reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY` and `OPENROUTER_API_KEY` from the environment. It sends each key only to its own provider's read-only "list models" endpoint and fetches the public models.dev catalog. Skip it and ModelScout uses the host's model lineup and the catalog.
- **Not present:** no telemetry, no background processes, no self-updating, no runtime patches of Hermes.

## License

MIT
