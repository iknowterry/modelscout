# Changelog

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
