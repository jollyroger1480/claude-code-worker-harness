---
name: arch-review
description: |
  After any multi-file code change, systematically apply 8 architectural
  checks before declaring done. Catches regressions, dead code, data model
  inconsistencies, and cross-component gaps that tests don't catch.
  Includes a dead-code sweep (check 6). Born from introducing a hardcoded
  wrong category in an agent prompt while removing dead code: tests passed,
  but the feature was broken.
allowed-tools: |
  Bash, Read
---

# Arch Review

<purpose>
Tests pass does not mean the code is correct. After any multi-file refactor or
removal, there are failure modes no test catches: agent prompts with hardcoded
wrong values, dead code that accumulated during the change, scripts that write
to a file nothing reads anymore, logging gaps on new error paths. This skill
forces the 8 checks before any "done" declaration.
</purpose>

## When To Activate

- After any change touching 3+ files
- After removing a function, class, or data format
- Before declaring any refactor complete
- When the user asks "are you sure?" or "double-check your work"
- Before committing or syncing to another machine

The commands below use `src/` and `app.py` as stand-ins; substitute your own paths.

## The 8 Checks

### 1. Separation of Concerns
Each module or function should do one thing. After a refactor, check for:
- Logic that leaked into the wrong layer (parsing in the API layer, API calls in parsers)
- Functions that now do less but still carry the old structure
- Cross-dependencies the refactor didn't clean up

```bash
# Find remaining references to removed concepts
grep -rn "OLD_THING\|old_function\|legacy_path" src/ --include="*.py"
```

### 2. Sequence of Operations
Verify the data flow still holds after the change:
- Is the new first step actually reachable?
- Are there early-exit paths that bypass required setup?
- Does every caller still pass arguments in the right order?

```bash
# Trace the call chain for the main entry points
grep -rn "def main\|def run\|def handle_" src/
```

### 3. Object Instantiation / Attribute Misses
After removing a code path, check every object that flowed through it:
- Are there attributes that were set ONLY in the removed path?
- Will callers of modified functions hit a KeyError or AttributeError?
- Was any object initialization moved that downstream code still expects?

```bash
# Dict keys that may only have been set in the removed code
grep -rn "fields\['" src/
```

### 4. Data Model Consistency
The hardest one. After format changes, check:
- Do ALL writing paths use the new format?
- Do ALL reading paths accept the new format?
- Are any hardcoded values (category IDs, policy IDs, status codes) specific to one
  item type but used in generic paths?

**Red flags:**
- A script that reads format A but writes format B
- A prompt or template with hardcoded IDs that should be dynamic
- IDs that differ by item type but are used uniformly

```bash
# Find every place that WRITES the file format you changed
grep -rn "write_text\|\.write(" src/ --include="*.py" | grep -i "record\|export"

# Find hardcoded numeric IDs in prompt strings
grep -rnE "[0-9]{6,}" src/prompts/ | head -20
```

### 5. Syntax / Import Check
After removing functions:
```bash
python3 -m py_compile $(git diff --name-only -- '*.py')
```

After removing imports, verify nothing still references them:
```bash
git diff --name-only | xargs grep -n "from\|import" | grep -v "^Binary"
```

### 6. Dead Code Sweep
Every removed function may have left behind:
- Helper functions it was the sole caller of
- Compiled regex patterns used only by it
- Constants only referenced from it
- Type aliases or imports only needed by it

```bash
# Private functions defined but never referenced again in the same file
grep -n "^def _" app.py | while IFS=: read -r line content; do
  fname=$(echo "$content" | grep -o '_[a-z_]*' | head -1)
  count=$(grep -c "$fname" app.py)
  [ "$count" -le 1 ] && echo "DEAD: $fname (line $line)"
done
```

### 7. Logging / Tracing
On new error paths introduced by the refactor:
- Every `return "ERROR: ..."` should have a log call before it
- Removed conversion steps that had log calls need replacement log coverage
- New success paths should log at the same granularity as old ones

```bash
grep -rn 'return.*ERROR\|return.*error' src/ | head -20
```

### 8. Cross-Component / Architectural Consistency
The most commonly missed check. After changing one script, enumerate all OTHER
scripts that interact with the same data:
- Scripts that READ what you changed to WRITE
- Scripts that WRITE what you changed to READ
- Agent prompts that describe the format to the LLM

```bash
# After changing a file format, find all scripts that touch that format
grep -rln "record.txt\|RECORD_FORMAT" src/ --include="*.py"
# For each result: does it read? write? both? Is it now inconsistent?
```

## Confidence Rating

After all 8 checks, rate 0-10:
- 10: All 8 clean, tests pass, no cross-component gaps
- 7-9: Minor dead code or cosmetic issues, no behavior regressions
- 5-6: One data model inconsistency or one half-migration
- 3-4: Regression introduced, agent prompts have wrong hardcoded values
- 0-2: Multiple broken paths, tests mask the failures

## NEVER

- Declare "done" after tests pass without running the 8 checks
- Hardcode item-type-specific values in generic code paths
- Leave dead helper functions after removing their only caller
- Change a READ path without checking the WRITE path (and vice versa)
- Forget that agent prompts are code: wrong hardcoded values in prompts are regressions

## ALWAYS

- Run all 8 checks after any multi-file change
- After removing a data format, grep for ALL writers and ALL readers of that format
- Check for hardcoded IDs in prompts and templates; they rot when item types change
- Give a confidence rating with specific reasons, not just "looks good"

## The failure that spawned this skill

An old bracket-style record format was removed from a pipeline. All 477 tests
passed. But:
1. The agent prompt was updated with one hardcoded category ID and condition code
   for ALL requests, which was wrong for most item types.
2. One relist script still WROTE the old format, so the new file was never
   updated and the verifier saw stale data.
3. Two helpers and a regex were left as dead code after their sole caller was removed.
4. One more parser helper in the verifier was left as dead code.

None of these were caught by tests. All were caught by the 8-check review.
