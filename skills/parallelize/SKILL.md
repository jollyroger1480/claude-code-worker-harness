---
name: parallelize
description: >
  When work splits into independent, substantial subtasks (research N topics,
  analyze N files, test N scenarios), consider parallel agents instead of doing
  them one after another in the main context. Pick the pattern by dependency
  shape: fan-out, pipeline, or map-reduce. Claude sub-agents go through the
  model-router workers (quick-worker, routine-worker, opus-worker, architect).
  Small or quick work stays inline.
---

# Parallelize

<purpose>
Doing independent subtasks one at a time in the main context burns tokens and
wall-clock time, and fills the main window with intermediate results. Offload to
parallel agents; keep only the conclusions. The only real difference between
"fan out", "map-reduce" and "pipeline" is the dependency shape, captured below.
</purpose>

## When To Activate

- A task has more than 3 independent subtasks (research, file analysis, test scenarios).
- A batch job has more than 30 items OR will run longer than 15 seconds.
- Any "do X to everything, then summarize" shape.

## Pick the pattern by dependency shape

**Fan-out** (subtasks fully independent, you want all results):
Spawn one agent per subtask, run concurrently, aggregate. Barrier at the end.
Use for: research multiple topics, analyze multiple files, N independent checks.

**Pipeline** (each item flows through ordered stages, items independent of each other):
Each item goes stage1, stage2, and so on; item A can be in stage 3 while item B is in stage 1.
NO barrier between stages. Wall-clock = slowest single chain, not sum of stages.
Use for: design, implement, test per feature; find, verify per finding.

**Map-reduce** (process all, THEN combine; the combine needs the full set):
Map: process each item independently (parallel). Reduce: aggregate all results.
The barrier between map and reduce is REQUIRED (reduce needs everything).
Use for: codebase-wide analysis then summary, dedup across all findings, count or rank.

Default to pipeline unless the reduce step genuinely needs all results at once.

## Where to run it: model-router workers

A Claude sub-agent spawn is routed by the model-router PreToolUse hook
(`guard_agent_model.py`, table in `routing.json`). Name the worker that fits:

- `quick-worker` (cheapest tier): status, grep, where-is lookups.
- `routine-worker` (mid tier): read a document or log and report what it says.
- `opus-worker` (top coding tier): a file has to change or code has to be written.
- `architect` (top reasoning tier): system design, an architecture decision, a plan review.
- Code or security review: not a sub-agent. Run `ocr review --audience agent`.
- Odd chores (a blurb, a rename list, a one-file summary): skill `lowtier`, which
  either does it inline or hands it to the optional cheap lane (`bin/grok-leaf`).

## NEVER
- Do N independent, substantial subtasks sequentially in the main context when they can fan out.
- Spawn an agent for a handful of tool calls or a lookup whose target you already know.
- Use a map-reduce barrier when a pipeline (no barrier) would finish faster.

## ALWAYS
- Name the dependency shape first, then pick fan-out, pipeline or map-reduce.
- Keep only conclusions in the main context; let agents hold the intermediate data.
- Probe ONE item end to end before fanning out a batch (see [[probe-before-batch]]).
- Fan out only when the work is truly independent **and** worth the cost. When in
  doubt, do it inline.
