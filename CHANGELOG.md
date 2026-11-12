# Changelog

## [0.3.7] - 2026-11-12

### Added
- Native Hermes Agent plugin (`plugin.yaml` + `__init__.py`). It registers:
  - the `pre_llm_call` card hook in-process (no `config.yaml` edit needed);
  - the `modelscout:modelscout` skill;
  - a `/modelscout` slash command.
  Settings commands are answered without a model call. Passes `hermes plugins validate` and `hermes plugins doctor --ci` on Hermes v0.23.0
- `plugins/modelscout/README.md`: plugin page text with full disclosures
- `savings.py`: `text_report()` for in-process use; honours `HERMES_HOME`

### Changed
- The hook loads `prefs.py` / `savings.py` by path under private module names (no `sys.path` edits, no subprocess for `savings`)
- `modelscout: status` now says "ModelScout settings" instead of "settings saved"
- `discover-models.sh` sends the Gemini key in the `x-goog-api-key` header instead of the URL

### Fixed
- Only recognised settings (`auto`, `status`, `T1 stay`…) count as `modelscout:` commands. Before, a delegated goal such as "ModelScout: rename the field…" was blocked as a settings command, so the routed task never ran (all hosts)
- Hermes: a `subagent_start` hook marks delegated children, so a child never gets a card or re-routes the task it was given
- Regression tests in `tests/test_commands.py`

## [0.3.6] - 2026-11-06

### Added
- Plugin icon (telescope with a sparkle on an indigo → violet → cyan gradient) in `plugins/modelscout/assets/`: `icon.svg`, `icon-dark.svg` and a 512×512 `icon.png`
- Claude Code manifest: `icon`, `repository`, `documentationUrl` and `supportUrl`
- Codex / ChatGPT plugin page: `logo`, `logoDark`, `composerIcon`, `brandColor`, `websiteURL` (it showed "Unavailable"), `developerName`, short and long descriptions, and three suggested prompts

## [0.3.5] - 2026-11-06

### Fixed
- Short follow-ups that open with an acknowledgement plus a brief clause ("yes, test it", "ok, go on", "no, use postgres instead", "ได้เลย ทดสอบด้วย") no longer get a routing card. A prompt counts as a follow-up when it is 30 characters or less and has at most 3 words after the acknowledgement; task keywords still win, and "sure, write a poem about cats" still counts as a new task ([#1](https://github.com/iknowterry/modelscout/issues/1), reported by @Kanyarit)

### Added
- `tests/test_is_trivial.py`: regression cases for the follow-up filter (`python3 -m unittest discover tests`)

## [0.3.4] - 2026-11-06

### Added
- Savings report reads Hermes Agent's session database (`~/.hermes/state.db`, read-only): delegated child sessions whose goal starts with `ModelScout:`, with per-model token usage and run time
- Savings are now compared by price, not by Claude model family, so OpenAI, Gemini and mixed-provider routes (e.g. GPT → Claude) are priced correctly from the models.dev catalog

### Changed
- New positioning everywhere (README, skill, manifests): ModelScout knows which models you actually have, picks the right one for every task, and proves what that saved, across every agent
- On non-Claude hosts (Hermes `delegate_task`), the routing rule tags delegated goals with `ModelScout:` so savings can be measured

## [0.3.3] - 2026-11-06

### Added
- Hermes Agent support:
  - `hermes skills install iknowterry/modelscout/plugins/modelscout/skills/modelscout` installs the skill; Hermes's security scan rates it SAFE
  - The prompt hook understands Hermes's `pre_llm_call` shell-hook payload and replies in Hermes's `{"context": …}` format, using the current model reported in the payload
  - Tested with Hermes v0.22.7

## [0.3.2] - 2026-11-06

### Changed
- The per-task card now stands out from normal replies: a quote block with a code-styled `🔭 ModelScout` badge, bold tier, highlighted model names and a ⚡ action line (Claude Code, Codex, Gemini and claude.ai)

## [0.3.1] - 2026-11-05

### Fixed
- Savings report showed 0 min of run time for subagents that ran in the background; duration now falls back to the subagent log's own timestamps
- Run times under a minute are shown in seconds

## [0.3.0] - 2026-11-05

### Added
- Per-task ModelScout card on every new task: tier, best-fit model, a one-line reason, and what happens next, in the user's language
- Default `auto` mode routes each mismatched task straight to a best-fit subagent, up-tier (Opus) as well as down (Haiku/Sonnet), then verifies the result
- `ask` mode popup: Run in subagent / Stay / Always subagent for this tier / Always stay for this tier
- Per-tier defaults (`modelscout: T1 stay`, `modelscout: T3 ask`) that override the mode; new `inform` and `off` modes
- `/modelscout:prefs` command: view and change defaults through a popup
- `scripts/prefs.py`: the single writer of the profile; keeps other fields like declared subscriptions
- Current-model detection from the session transcript, including `/model` changes made mid-session

- Measured savings report: `modelscout: savings` or `scripts/savings.py` reads Claude Code transcripts and reports tokens on lighter models, the cost-weighted % saved (= share of quota freed for subscribers), main-model budget freed, and measured run time. API messages are deduplicated, and every price used is named
- Cross-host packaging based on the open Agent Skills standard:
  - Codex CLI and the ChatGPT desktop app install with `codex plugin marketplace add iknowterry/modelscout` (root `plugin.json` plus `.agents/plugins/marketplace.json`)
  - Gemini CLI gets `gemini-extension.json` and `BeforeAgent` hook support
- Host-aware hook output (JSON `additionalContext` everywhere); Codex and Gemini get price-band model picks from the user's inventory or the catalog

### Changed
- Repo layout: the plugin now lives in `plugins/modelscout/`, and the skill is self-contained (`references/heuristics.md`, `scripts/`), so a standalone skill install works on any host
- SKILL.md follows the agentskills.io spec (license, compatibility, metadata) and is written by host capability rather than for Claude only
- Removed the paste-in Codex and Gemini adapters; native plugin and skill installs replace them
- The hook now injects a compact block on every new task prompt instead of once per session, so ModelScout stays active in long sessions and after compaction
- `modelscout: …` settings commands are handled inside the hook: saved instantly, with no model turn
- Short follow-ups ("yes", "continue", "ต่อเลย") never trigger a card
- Legacy `"mode": "suggest"` profiles are read as `ask`

## [0.2.1] - 2026-07-17

### Added
- SessionStart hook: announces "ModelScout active" in the first working reply so users see it running from prompt one
- Always-on tier receipts by default ("T2 — model fits" on every real task); "modelscout: quiet receipts" reverts to mismatch-only
- Stronger (MANDATORY) instruction framing so per-task tier classification is never skipped

## [0.2.0] - 2026-07-09

### Added
- Proactive mode: suggest model switches via hooks without being asked, with one-line nudges on mismatches and popup prompts on large ones
- Auto mode: automatically route mechanical tasks to right-sized subagents based on task complexity
- Mode configuration via ~/.claude/modelscout-profile.json with "Always auto-route" toggle
- Hook auto-registration for plugin installs

## [0.1.0] - 2026-07-09

### Added
- Inventory-grounded AI model recommendations based on user's API keys and subscriptions
- Core discovery script supporting Anthropic, OpenAI, Gemini, and OpenRouter
- T1-T4 task-tier heuristics with price-band mapping and honesty rules
- Claude Code adapter with subagent routing and /model advice command
- Adapters for Codex AGENTS.md, Gemini CLI, and ChatGPT Custom GPT
- No-key path: declared subscriptions via ~/.claude/modelscout-profile.json
- Live pricing data integration from models.dev
