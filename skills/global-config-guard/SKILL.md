---
name: global-config-guard
description: >
  Before editing anything machine-global that several Claude Code projects
  share (the user settings.json, the global skills and hooks folders, crontab,
  shell rc files, systemd user units), stop and check the blast radius across
  the OTHER projects on the machine. Scope hook matchers to an exact path, and
  when you delete or rename a global skill, fix every project's permission
  allowlist that referenced it. Prevents a change made for one project from
  silently breaking the others.
allowed-tools: |
  bash: grep, find, python3, jq
  file: read
---

# Global Config Guard

<purpose>
One machine often runs several distinct Claude Code projects: say a media
toolkit, a shop backend and a document project. They are separate conversations
but share ONE global config tree: `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json`,
its `skills/` and `hooks/` folders, plus machine state (crontab, `~/.bashrc`,
systemd user units). A change made while working on one of them silently reaches
all of them. A hook with a `*/scripts/*` matcher fires on every project's scripts;
deleting a "redundant" global skill orphans another project's permission
allowlist. The fix is a 30-second blast-radius check before editing anything global.
</purpose>

## When To Activate

Before editing, deleting or creating any of:
- the user `settings.json` or any `.claude/**/settings*.json` (hooks, permissions, env)
- global skills (creating, merging, deleting, renaming a skill)
- global hooks
- `crontab`, `~/.bashrc` / `~/.profile`, `~/.config/systemd/user/*`, global env

## Instructions

### 1. Name every context that shares this global thing
```bash
find "$HOME" -maxdepth 3 -path "*/.claude/*settings*.json" 2>/dev/null
ls -d "$HOME"/*/.claude 2>/dev/null   # per-project contexts
```
Assume every project with a `.claude/` folder is live unless proven otherwise.

### 2. Scope hook matchers to an EXACT path, never a wildcard that spans contexts
- BAD:  `"$file" == */scripts/*.py`   (catches every project's scripts folder)
- GOOD: `"$file" == "$HOME/media-tools/scripts/"*.py`   (only the intended one)

Then SIMULATE: run the matcher against a file from each OTHER context and confirm it does NOT fire.

### 3. When deleting or renaming a global skill, repair every consumer
```bash
grep -rl "Skill(<old-name>)" "$HOME"/*/.claude/settings.local.json
```
Remap each context's permission allowlist entry to the replacement skill so the
other projects keep their auto-approval (a deleted skill's permission silently
becomes a prompt there). Also grep your notes for links to the old name.

### 4. Validate every file you touched is still parseable
```bash
for f in <each settings.json touched>; do python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$f"; done
```

## NEVER
- Edit global Claude config while "in" one project without checking the others.
- Use a `*/dir/*` hook matcher when you mean one specific absolute path.
- Delete or merge a global skill without remapping every context's `Skill(...)` permission.
- Assume "this session is separate" means "my config change is isolated". Conversations
  are separate; the config dir is shared.

## ALWAYS
- Enumerate the sibling projects before a global edit.
- Anchor hook matchers to absolute paths and simulate against each context.
- Back up settings.json before editing; validate JSON after.
- Cross-reference [[trace-it]] (the same principle for shared CODE). This is its config twin.

## The failure that spawned this skill
While cleaning up one project's skills, global skills were merged and deleted and
PostToolUse hooks were added with `*/scripts/*` matchers. Both bled into the other
projects: the hooks would have fired on their script edits, and the deletions
orphaned several `Skill(...)` entries in their permission allowlists. The user
caught it, not the agent. The blast-radius check should have run before the global
edits, not after.
