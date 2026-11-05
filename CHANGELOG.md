# Changelog

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
