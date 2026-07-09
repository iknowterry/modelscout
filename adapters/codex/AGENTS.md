# ModelScout — Codex CLI adapter

Paste this section into your `~/.codex/AGENTS.md` (or a project `AGENTS.md`),
and copy the `core/` directory to `~/.modelscout/core/` (or clone this repo and
adjust the paths).

---

## Model advice (ModelScout)

When I ask which model to use, whether a model is overkill, or how to cut LLM
costs:

1. Ensure the inventory is fresh (missing or >7 days old → rebuild):
   `bash ~/.modelscout/core/discover-models.sh`
2. Read `~/.claude/model-inventory.json` (models my keys can access, with
   pricing) and, for context on models I *don't* have,
   `~/.claude/model-catalog.json`.
3. Follow the recommendation logic in `~/.modelscout/core/heuristics.md`:
   classify the task into a tier (T1 economy → T4 frontier), apply the
   capability modifiers, and recommend the cheapest available model that clears
   the bar — with a runner-up, a small cost table, and the honesty rules
   (bias up-tier when uncertain; never suggest a model I don't have).
4. Acting on it: for this Codex session suggest the `/model` command with the
   exact model id; for other tools give me the copy-pasteable model id from the
   inventory.
