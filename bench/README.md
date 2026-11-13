# ModelScout benchmark

This benchmark checks whether ModelScout saves money without losing quality. It runs the same tasks twice, on the same main model and in a fresh copy of the same project: once with ModelScout off, once with it on. Each result is checked with hidden tests.

## What it measures

- **Cost, net.** Every API request in the main session and in every subagent counts, each priced by the model that served it at models.dev prices. Both arms use the same prices. The routed arm pays for the main model's briefing and for checking the subagent's work, and those costs are included. So this is the real difference, not the upper bound `modelscout: savings` shows.
- **Quality.** A run passes only if the task's hidden tests *and* the project's own tests pass. The agent never sees the hidden tests; they are copied in after it finishes.
- **Time and routing.** Wall-clock time, and how many subagents ModelScout used and on which models.

## Tasks

12 tasks on a small Python project (`fixture/`), written the way a developer would ask:

| Tier | Count | Kind of work |
|---|---|---|
| T1 mechanical | 4 | renames, type hints, docstrings, a config option |
| T2 standard | 5 | a feature with tests, a bug from a stack trace, a CLI subcommand, a CSV column, unit tests |
| T3 hard | 3 | a planted subtle bug, a de-duplicating refactor, an ordering-sensitive issue |

Each task in `tasks/<id>/` has `task.json` (the prompt), an optional `setup/` (applied before the run, e.g. a planted bug), the hidden `check/` tests, and a reference `solution/`. `validate_tasks.py` proves, without any model, that every check fails before the work and passes with the reference solution. The repo's test suite runs it.

## Fairness and isolation

- Both arms run with `--setting-sources project --strict-mcp-config`, and your installed ModelScout is disabled for the run. Your other plugins, user hooks and MCP servers don't load either. Only the routed arm adds `--plugin-dir plugins/modelscout`, the code in this repo.
- A run is **invalid** and left out if ModelScout's hook block appears in a baseline transcript or is missing from a routed one.
- Savings are computed only on tasks with valid runs in both arms.
- Runs are shuffled so both arms meet the same time of day and the same rate limits.
- `MODELSCOUT_STATE_DIR` gives each run its own ModelScout settings (mode `auto`) and outcome log, so your real settings and learning are untouched. Your `modelscout: savings` report skips benchmark sessions.
- Edits are auto-accepted inside the temp copy only. Bash may run the tests (`python3 -m unittest`, `pytest`) and `ls`/`wc`/`diff`. Web tools, `curl`, `wget`, `git`, `ssh`, `rm` and `sudo` are denied. The hidden and visible checks run with a scrubbed environment: no API keys, no cloud credentials, no real HOME.
- **Know the risk:** the agent writes code and the tests run it, so this is arbitrary code execution as your user. Permissions limit it, but it is not a sandbox. The prompts are benign and written in this repo. For real isolation, run the benchmark in a container or a throwaway user account.

## Run it

It spends real tokens: your subscription's usage quota or API credit. Without `--go` it only prints the plan.

```bash
python3 bench/validate_tasks.py                              # free: checks the task set
python3 bench/run.py                                         # free: prints the plan
python3 bench/run.py --go --tasks <one T1 task id>           # smoke test: 2 runs, confirms isolation
python3 bench/run.py --go --repeat 3                         # full: 12 tasks × 2 arms × 3 = 72 runs
python3 bench/report.py bench/results/<run folder>           # the table (also written to summary.md)
```

Use `--model` to set the main model (default `opus`), and `--keep` to keep the temp project copies for inspection. Results are saved as one JSON file per run under `bench/results/`, so anyone can re-check the numbers.

Run the smoke test first. If either run comes back INVALID, the isolation assumption doesn't hold on your Claude Code version, and the full run would measure the wrong thing.

## Reading the result

The report shows cost with and without ModelScout per tier and overall, pass rates side by side, where the routed arm's money went (main model vs subagent models), and any task whose pass rate dropped with ModelScout. Publish the number together with the pass rates and the run folder. A saving with a lower pass rate isn't a saving.
