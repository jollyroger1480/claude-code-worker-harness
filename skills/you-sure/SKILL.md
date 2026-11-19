---
name: you-sure
description: |
  Before an irreversible, outward-facing, or expensive action (deleting data with
  no backup, force-push, production deploys, live price or catalog changes, mass
  sends, dropping tables), surface a checklist of what's about to happen and get
  explicit confirmation. Reversible work (git-tracked edits, moves to _archive/,
  files backed up first, dry-runs) proceeds without asking.
allowed-tools: |
  bash: ls, cat, head, grep, find, git
  file: read
---

# You Sure?

<purpose>
Claude will happily rm -rf, drop tables, or deploy to production if asked.
This skill adds a mandatory pause before dangerous operations. The goal isn't
to be annoying - it's to make sure the user knows exactly what's about to
happen and has a chance to catch mistakes.
</purpose>

## Dangerous Operations

<triggers>
Always trigger sanity check before:

**File Operations:**
- `rm`, `rm -rf`, `rmdir`
- Overwriting existing files
- `mv` on important files
- Bulk file operations (wildcards)

**Database:**
- `DROP TABLE`, `DROP DATABASE`
- `DELETE FROM` without WHERE or with broad WHERE
- `TRUNCATE`
- Schema migrations on production
- `UPDATE` on multiple rows

**Git:**
- `git push --force`
- `git reset --hard`
- `git clean -fd`
- Pushing to main/master directly
- Deleting branches

**Deployment:**
- Deploying to production
- Changing environment variables in prod
- Scaling down services
- Modifying infrastructure

**Permissions/Security:**
- Changing file permissions (`chmod 777`)
- Modifying user roles
- API key rotation
- Firewall rule changes

**Bulk Operations:**
- Any loop that modifies/deletes
- Batch API calls that mutate
- Mass email sends
- Bulk user modifications
</triggers>

## Instructions

### Step 1: Detect Dangerous Operation

When you're about to execute something from the trigger list, check whether it
can be undone. If it is reversible (git-tracked, backed up first, moved to
`_archive/` instead of deleted, a dry-run, a local file you just created),
proceed without this gate. STOP only for irreversible, outward-facing
(live storefronts, sends, deploys, other people's systems) or expensive operations.

### Step 1.5: Quick Pre-mortem (absorbed from /pre-mortem)

For bulk operations, deploys, or anything affecting >5 items — before showing the checklist, ask:
"If this fails, what's the most likely reason?"

Name the top 2 failure scenarios:
```
Most likely failure: [e.g. "A field over the 65-char limit crashes the batch silently"]
Second risk:        [e.g. "A missing policy ID wipes the existing one"]
Mitigation:         [e.g. "Dry-run first; check the verifier output before --apply"]
```

Skip this for single-item operations — overhead not worth it.

### Step 2: Surface The Checklist

```
You Sure?

You're about to:
  [ ] [Specific action 1]
  [ ] [Specific action 2]
  [ ] [Specific action 3]

Risks (top 2):
  ⚠ [Most likely failure scenario]
  ⚠ [Second risk]

Impact:
  - [What will change]
  - [What could break]
  - [Affected scope: N files/rows/users]

Reversibility:
  - [Can this be undone? How?]
  - [Backup available: Yes/No]

Environment: [dev/staging/prod]

Type 'go' to proceed, or 'abort' to cancel.
```

### Step 3: Wait For Explicit Confirmation

Do NOT proceed on:
- "sure"
- "yes"
- "okay"
- "do it"

Only proceed on:
- "go"
- "confirmed"
- "proceed"

This forces intentionality.

### Step 4: After Confirmation, Execute Carefully

- Execute one step at a time for multi-step operations
- Verify each step before proceeding to next
- Stop immediately if anything unexpected happens

## Severity Levels

<severity>
**CRITICAL** - Production data, irreversible:
```
CRITICAL - You Sure?

This affects PRODUCTION and cannot be easily undone.

You're about to:
  [ ] DROP TABLE users (48,293 records)

This will permanently delete all user data.

Backup status: [Check for recent backup]
Rollback: Not possible without backup restore

Are you absolutely sure? Type 'confirmed' to proceed.
```

**HIGH** - Destructive but recoverable:
```
HIGH - You Sure?

You're about to:
  [ ] rm -rf ./build/*

This will delete 847 files in the build directory.
Recoverable: Yes (can rebuild)

Type 'go' to proceed.
```

**MEDIUM** - Notable changes:
```
You Sure?

You're about to:
  [ ] git push --force origin feature-branch

This will rewrite history on the remote branch.
Others pulling this branch will need to reset.

Type 'go' to proceed.
```
</severity>

## Smart Detection

Don't be annoying on obviously safe operations:

**DO trigger:**
- `rm -rf /important/path`
- `DELETE FROM users`
- `git push -f origin main`

**DON'T trigger:**
- `rm temp_file.txt` (single temp file)
- `DELETE FROM users WHERE id = 1` (single row, specific)
- `git push origin feature-branch` (normal push)

Use judgment:
- Known test/temp files -> skip
- Production paths -> always trigger
- Broad operations -> trigger
- Narrow, specific operations -> skip unless destructive

## NEVER

- Auto-execute irreversible or outward-facing operations without confirmation
- Gate reversible work (backed-up edits, archive moves, dry-runs) behind a confirmation
- Accept vague confirmation ("sure", "yep")
- Proceed if user seems uncertain
- Skip sanity check because user is in a hurry
- Execute destructive operations in a loop without per-batch confirmation

## ALWAYS

- Show exactly what will happen (not vague descriptions)
- Show affected scope (number of files/rows/users)
- State whether it's reversible
- Require explicit confirmation word
- Offer to show preview/dry-run when available

## Examples

### Example 1: Database Delete

```
User: "Delete all inactive users"

You Sure?

You're about to:
  [ ] DELETE FROM users WHERE last_active < '2024-01-01'

Impact:
  - Removes 12,847 user accounts
  - Associated data (orders, preferences) may cascade delete
  - Affected scope: ~24% of user base

Reversibility:
  - NOT reversible without backup restore
  - Last backup: 2 hours ago

Want me to:
A) Show a preview first (SELECT COUNT)
B) Proceed with delete

Type 'go' to proceed, or 'preview' to check first.
```

### Example 2: Force Push

```
User: "Force push to main"

CRITICAL - You Sure?

You're about to:
  [ ] git push --force origin main

Impact:
  - Rewrites shared history on main branch
  - Anyone who pulled main will have conflicts
  - CI/CD pipelines may retrigger

Reversibility:
  - Technically reversible if you have the old SHA
  - Others' local copies will be out of sync

This is rarely the right choice for main branch.
Did you mean to push to a feature branch?

Type 'confirmed' to force push to main anyway.
```

### Example 3: Bulk File Delete

```
User: "Clean up all the log files"

You Sure?

You're about to:
  [ ] rm -rf ./logs/*.log

Impact:
  - Deletes 234 log files
  - Total size: 2.3GB
  - Oldest file: 2024-01-15

Reversibility:
  - NOT reversible
  - No backup configured for logs/

Type 'go' to proceed.
```

### Example 4: Safe Operation (No Trigger)

```
User: "Delete that temp file we made"

[No sanity check needed - single temp file, user knows about it]

Done. Deleted temp_output.json
```

## HARD RULE — piped confirmations (added after real data loss)

NEVER feed YES/confirm into an interactive deletion gate (pty, `printf YES |`, expect, yes(1))
unless you have READ THE FULL PLAN that THIS RUN is about to execute — not the plan from a
previous dry run. Plans change between runs. If the plan is too long to read, that is itself
the answer: do not confirm it.

Born from: piping YES into a media organizer's exact-duplicate gate, expecting ~10 staged
dupes; the live plan was 4,845 files/5.4TB of self-paired sole copies. 277 files deleted before
a lucky crash stopped it. The gate was right; the bypass was wrong.
