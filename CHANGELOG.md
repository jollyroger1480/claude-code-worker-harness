# Changelog

## 2026-11-20: reasoning effort per worker

Each worker file in `agents/` now pins a reasoning effort as well as a model, so cheap jobs stop thinking as hard as expensive ones.

| Worker | Model | Effort |
|---|---|---|
| `quick-worker` (lookup) | `claude-haiku-5-5` | `low` |
| `routine-worker` (read) | `claude-sonnet-5-5` | `low` |
| `opus-worker` (execution) | `claude-opus-5-5` | `medium` |
| `architect` (design) | `claude-fable-5-2` | `high` |

Why: the router already chose the cheapest model that fits the job, but effort was left unset. A worker on a different model than the main session does not take the session's level, so lookups and reads ran at their model's default. Pinning it per worker is the missing half of the saving.

To change a level, edit the `effort:` line in the worker file (`low`, `medium`, `high`, `xhigh` or `max`). A single call can still pass its own `effort`, and the `CLAUDE_CODE_EFFORT_LEVEL` environment variable overrides everything. Existing installs: run `install.sh` again, or add the `effort:` line to your four worker files by hand.

Tests: two new checks fail if a worker has no valid effort, or if a cheap worker is set higher than an expensive one.

## 2026-11-19: first release

Model router, context budget, guards, the cheap lane, demo video.
