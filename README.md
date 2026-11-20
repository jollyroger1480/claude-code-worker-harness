# Claude Code Worker Harness

![A ship's helm linked to six lit workbenches: one lead, many workers](assets/hero.jpg)

A small set of Claude Code hooks, agents and skills that make the main Claude session act as a lead: it keeps the hard thinking and hands each job to the worker that suits it. File changes go to an execution worker, long reads go to a cheaper read worker, lookups go to the cheapest one, and odd chores go to a cheap lane outside Claude. That lane uses the Grok CLI by default, but any cheap agent CLI fits there.

https://github.com/user-attachments/assets/85ebec4d-7ef8-487c-bfe0-62bf4d6b4b76

One-minute demo ([file in this repo](assets/harness-demo.mp4)). Every terminal pane in it is the real hook run on sample calls. Music: "Arturia Acid" by Doctor_Dreamchip, CC0, from Freesound.

Free to use. If it saved you time, tips are welcome: [Cash App](https://cash.app/$jollyroger1480) or Bitcoin `bc1qydycnf5pjhez5d0mrgmmumyv2g5nc63mwet89j`. More links at the [bottom](#support-and-links).

## The routing idea

Every `Agent` (or `Task`) call goes through one PreToolUse hook, `hooks/model-router/guard_agent_model.py`. It reads the job description and the top of the prompt, works out what kind of job it is, and sets `subagent_type` to the matching worker. It also strips any `model` argument, because the model is pinned in each worker's agent file.

| Role | Worker (`agents/*.md`) | Default model | Gets |
|---|---|---|---|
| Lead | the main session | your session model | planning, judgment, final checks |
| Execution | `opus-worker` | `claude-opus-5-5` | code changes, file edits, running a task |
| Architecture | `architect` | `claude-fable-5-2` | design decisions, plan reviews |
| Read | `routine-worker` | `claude-sonnet-5-5` | read a document or log and report back |
| Lookup | `quick-worker` | `claude-haiku-5-5` | status, grep, where-is questions |
| Review | `code-reviewer`, `security-reviewer` | none | stubs that point Claude at the `ocr` review CLI |
| Cheap lane | `lowtier` skill + `bin/grok-leaf` | Grok CLI, or any CLI you plug in | short self-contained chores, image prompts |

Rules the guard applies:

- A plain `general-purpose` spawn goes to the read worker unless the prompt contains `OPUS-REASON:` followed by a reason. Expensive workers have to be asked for on purpose.
- Hard-thinking words in the job (solve, debug, investigate, audit and similar) are never sent to the read or lookup worker.
- `subagent_type: lowtier` is denied with a message that points Claude to the `lowtier` skill, because that work should not start a Claude sub-agent at all.
- Built-in types `Explore`, `Plan`, `fork`, `claude-code-guide`, `statusline-setup` and `web-fetch` pass through untouched.
- Bad hook input never blocks a call: the hook exits quietly and Claude Code carries on.

The roles, model ids and thresholds live in `hooks/model-router/routing.json`. Set `MODEL_ROUTER_CONFIG` to use a different file.

## How the context budget works

`hooks/model-router/context_budget.py` runs on every prompt (UserPromptSubmit). It reads the token usage of the last reply from the end of the session transcript (the last 2 MB only, so it stays fast) and speaks up at three points set in `routing.json`:

- `context_delegate_tokens` (120k): hand long reads to the read and lookup workers instead of reading them in the main session.
- `context_warn_tokens` (150k): compact at the next natural break.
- 85% of `context_limit_tokens` (170k of 200k): compact now.

Each note is said once per session. The hook never compacts, deletes or edits anything itself. It keeps a small state file per session in `${MODEL_ROUTER_STATE_DIR:-${XDG_CACHE_HOME:-~/.cache}/model-router}`.

## The other guard

`hooks/guards/no-self-matching-wait-loops.py` blocks a Bash command that waits on `pgrep -f` or `pkill -f` with a pattern that also matches the waiting shell itself. Such a loop never ends, because it keeps finding its own command line. The hook suggests waiting on a PID or using the bracket trick (`[m]yjob.py`).

## Requirements

- Claude Code with hooks and custom agents (`~/.claude/agents/`).
- Python 3.9 or newer, standard library only.
- Bash, coreutils (`timeout`, `tac`), `flock` from util-linux. On macOS install coreutils and util-linux from Homebrew.
- Optional: the [Grok CLI](https://x.ai/cli) for the cheap lane, and [Alibaba Open Code Review](https://github.com/alibaba/open-code-review) (`ocr`) for the review stubs.

## Install

```bash
git clone https://github.com/jollyroger1480/claude-code-worker-harness.git
cd claude-code-worker-harness
./install.sh --dry-run    # shows every file it would place and every hook it would add
./install.sh
```

What it does:

- Copies agents to `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/`, hooks to `.../hooks/claude-harness/`, skills to `.../skills/`, and `grok-leaf` to `${HARNESS_BIN_DIR:-~/.local/bin}`.
- An existing file with different content is moved to `<file>.bak.<timestamp>` first. Identical files are skipped, so running it again is safe.
- Adds the three hook entries from `settings.example.json` to your `settings.json` (after a backup) only if they are not there yet. Your other settings and hooks are left alone. Permissions are never changed; the ones in `settings.example.json` are examples to copy by hand if you want them.
- `--no-settings` skips `settings.json` so you can merge it yourself. `--no-grok-lane` skips `grok-leaf`.
- `./install.sh --uninstall` removes what it installed, puts the backups back and takes its hook entries out of `settings.json`.

Then edit the `model:` line in each `agents/*.md` to model ids your account offers (the defaults above may not exist on your plan), and start a new Claude Code session so the hooks load.

## Add a worker

1. Make `agents/<name>.md` with `name`, a one-line `description` that says when to use it, and `model`.
2. Add a role to `workflow` in `routing.json` with `subagent_types: ["<name>"]` and the same model.
3. If the guard should pick it by itself, add its keywords in `keyword_tier()` in `router_lib.py` and map the tier in `worker_name()`.
4. Add a test case to `tests/test_router.py` and run `tests/run_all.sh`.

## Cheap lane: Grok CLI for simple jobs and image generation

This setup uses Grok, through the `grok` CLI, as the cheap worker. Claude stays the lead: it decides what to send and checks every answer before using it. The `lowtier` skill tells Claude when a job is small enough (self-contained, easy to check, nothing private, no harm if wrong) and when to just do it inline.

`bin/grok-leaf` makes each call safe and boring:

- runs `grok --prompt-file ... --reasoning-effort low --max-turns 4 --disable-web-search` with stdin closed and a timeout (default 300 s); without closed stdin and low effort, headless calls can hang;
- runs Grok in an empty scratch folder, so its tools cannot touch your project unless you pass `--cwd`;
- never passes `--always-approve`, and refuses it if asked;
- refuses prompts that look like they contain a key or token;
- caps how many calls run at once (default 2);
- exits 3 with a clear message when grok is not installed, so Claude falls back to doing the job itself.

```bash
grok-leaf "Rewrite in plain English, under 60 words: <text>"
grok-leaf --dry-run "test"      # prints the exact command, spends nothing
```

Never send the cheap lane secrets, customer data, private files, or anything that changes a live system.

For images and video it pairs well with [grok-imagine-cli](https://github.com/jollyroger1480/grok-imagine-cli), which makes Grok Imagine stills, edits and clips from the terminal using the same Grok CLI login. Generations cost money or plan credits, so the skill tells Claude to ask before a batch.

### Use any cheap agent instead

The one place to change is the `CHEAP_LEAF_CMD` environment variable. Set it to any command that reads a prompt on stdin and prints an answer, and `grok-leaf` runs that instead of grok. The secret check, scratch folder, timeout and slot cap still apply.

```bash
export CHEAP_LEAF_CMD='llm -m some-cheap-model'     # Simon Willison's llm CLI
export CHEAP_LEAF_CMD='ollama run small-model'      # a local model
grok-leaf "Suggest five names for a log-rotation script"
```

To point at a grok binary that is not on `PATH`, set `GROK_BIN`.

## Tests

```bash
tests/run_all.sh
```

It byte-compiles the Python, runs the router and guard tests (sample hook JSON in, decisions out), syntax-checks the shell scripts (and runs shellcheck if you have it), runs `install.sh` for real and with `--dry-run` and `--uninstall` against a throwaway HOME, and checks that `grok-leaf` fails cleanly with no grok installed. Nothing touches your real config.

## Known issues and honest limits

- **Model ids are examples.** The defaults are the ids this was built with. Check them against your account before use; a wrong id makes the sub-agent call fail.
- **Rerouted calls are auto-approved.** When the guard rewrites a call it answers `allow`, which skips the permission prompt for that Agent call. If you want to approve each spawn yourself, change the final `emit("allow", ...)` in `guard_agent_model.py` to `"ask"`.
- **The classifier is keyword based.** It reads the description and the start of the prompt. Odd phrasing can land a job on the wrong worker; `OPUS-REASON:` and an explicit `subagent_type` override it.
- **The token count is an estimate.** It comes from the last usage block in the transcript, so the first prompt of a session and very large tool outputs can make it lag one turn.
- **Proxies that compress your messages.** If Claude Code talks through a compression proxy (set via `ANTHROPIC_BASE_URL`), check whether it compresses user messages. With user-message compression on, older turns of your own text reach the model with words dropped, which looks like Claude misreading you. For Headroom, set `HEADROOM_COMPRESS_USER_MESSAGES=0` on the proxy and restart it. This harness does not need a proxy.
- **Too many skills hide descriptions.** Claude Code caps the size of the skill listing. With a few hundred skills installed, some show with blank descriptions and are picked less often. Keep the skill folder lean.
- **The cheap lane is only as good as its checks.** `grok-leaf`'s secret check is a tripwire, not a guarantee, and a cheap model's answer is a draft. The `lowtier` skill tells Claude to verify; a hurried session may still skip it.
- **Linux first.** Built and tested on Linux. macOS should work with GNU coreutils and flock installed; Windows is untested.

## Also uses or credits

- The worker-routing idea comes from two public posts on X: [one](https://x.com/LanzhiAI/status/2122212822138650873) and [two](https://x.com/everyday_1123/status/2122192621099741497).
- Most method skills here are modified copies of [Claude-Skill-Potions](https://github.com/ElliotJLT/Claude-Skill-Potions) (MIT). `debug-to-fix` also borrows from [superpowers](https://github.com/obra/superpowers) (MIT). See `THIRD_PARTY_NOTICES.md`.
- [Alibaba Open Code Review](https://github.com/alibaba/open-code-review) for reviews.
- [grok-imagine-cli](https://github.com/jollyroger1480/grok-imagine-cli) for image and video work.

## Support and links

This project is free, and a tip is welcome but never expected.

- Tip (Cash App): [$jollyroger1480](https://cash.app/$jollyroger1480)
- Bitcoin: `bc1qydycnf5pjhez5d0mrgmmumyv2g5nc63mwet89j`
- eBay store: [Buccaneer Salvage](https://www.ebay.com/str/buccaneersalvage)
- YouTube: [@BuccaneerSalvage](https://www.youtube.com/@BuccaneerSalvage)
- X: [@jollyroger1480](https://x.com/jollyroger1480)

Not affiliated with Anthropic or xAI. Claude and Claude Code are Anthropic's; Grok is xAI's.

License: MIT.
