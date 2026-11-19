---
name: prove-it
description: |
  Before declaring any task complete, actually verify the outcome. Run the code.
  Test the fix. Check the output. Claude's training optimizes for plausible-looking
  output, not verified-correct output. This skill forces the verification step
  that doesn't come naturally. No victory laps without proof.
allowed-tools: |
  bash: python, node, npm, pytest, jest, cargo, go, make, cat, ls, grep
  file: read
---

# Prove It

<purpose>
Claude generates code by pattern-matching on training data. Something can look
syntactically perfect, follow best practices, and still be wrong. The model
optimizes for "looks right" not "works right." Verification is a separate
cognitive step that must be explicitly triggered. This skill closes the loop
between implementation and proof.
</purpose>

## The Iron Law (from superpowers verification-before-completion)

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in THIS message, you cannot claim
it passes. A previous run, "should pass," or extrapolating from a partial check
all count as not having verified.

## Why This Matters (Technical Reality)

<technical-honesty>
Claude's limitations that this skill addresses:

**1. Generation vs Execution**
I generate code but don't run it. I predict what it would do based on patterns.
My confidence comes from "this looks like working code I've seen" not from
"I executed this and observed the result."

**2. Training Signal Mismatch**
My training optimizes for plausible next-token prediction, not outcome
verification. Saying "Done!" feels natural. Verifying feels like extra work.
But verification is where correctness actually lives.

**3. Pattern-Matching Blindness**
Code that matches common patterns feels correct. But subtle bugs hide in the
gaps between patterns. Off-by-one errors. Wrong variable names. Missing edge
cases. These "look right" but aren't.

**4. Confidence-Correctness Gap**
High confidence in my output doesn't correlate with actual correctness.
I'm often most confident when I'm most wrong, because the wrong answer
pattern-matched strongly.

**5. No Feedback Loop**
I generate sequentially. I don't naturally go back and check. Without
explicit verification, errors compound silently.
</technical-honesty>

## Red Flags — STOP (from superpowers verification-before-completion)

Catch yourself before any of these leave your mouth without fresh evidence behind them:

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!")
- About to commit/push/PR without verification
- **Trusting a subagent's success report instead of checking its actual diff/output** —
  especially relevant when work is delegated to parallel agents;
  "agent said success" is not verification, check the VCS diff / real artifact yourself
- Relying on partial verification (one test file, not the suite; one file, not all changed)
- Thinking "just this once" or "I'm tired and want this over"
- ANY wording implying success without having run verification

## When To Verify

<triggers>
ALWAYS verify before declaring complete:

**Code Changes:**
- New functions or modules
- Bug fixes
- Refactoring
- Configuration changes
- Build/deploy scripts

**Fixes:**
- "Fixed the bug" - did you reproduce and confirm it's gone?
- "Resolved the error" - did you trigger the error path again?
- "Updated the config" - did you restart and test?

**Claims:**
- Factual statements that matter to the decision
- "This will work because..." - did you prove it?
- "The file contains..." - did you actually read it?
- "The backup captured X" — did you actually decrypt/list/diff and see X inside it,
  or just see the script exit 0?
</triggers>

## Instructions

### Step 1: Catch The Victory Lap

Before saying any of these:
- "Done!"
- "That should work"
- "I've implemented..."
- "The fix is..."
- "Complete"

STOP. You haven't verified yet.

### Step 2: Determine Verification Method

| Change Type | Verification |
|-------------|--------------|
| New code | Run it with test input |
| Bug fix | Reproduce original bug, confirm fixed |
| Function change | Call the function, check output |
| Config change | Restart service, test affected feature |
| Build script | Run the build |
| API endpoint | Make a request |
| UI change | Describe what user should see, or screenshot |
| Display / scale / app chrome | OCR the last screenshot numbers before claiming done |
| Backup/data capture | Decrypt/extract and confirm the specific item is actually inside |
| Agent-delegated work | Check the VCS diff or real output file, not the agent's summary |

### Step 3: Actually Verify

```bash
# Don't just write the test - run it
python -m pytest tests/test_new_feature.py

# Don't just fix the code - prove the fix
python -c "from module import func; print(func(edge_case))"

# Don't just update config - verify it loads
node -e "console.log(require('./config.js'))"
```

### Step 4: Report With Evidence

```
Verified:

What I changed:
  - Added input validation to user_signup()

How I verified:
  - Ran: python -c "from auth import user_signup; user_signup('')"
  - Expected: ValidationError
  - Got: ValidationError("Email required")

Proof that it works. Done.
```

## Verification Patterns

### Pattern 1: The Smoke Test

Minimal test that proves basic functionality:

```bash
# After writing a new function
python -c "from new_module import new_func; print(new_func('test'))"
```

If this crashes, you're not done.

### Pattern 2: The Regression Check

After fixing a bug, trigger the original failure:

```bash
# Bug was: crash on empty input
python -c "from module import func; func('')"
# Should not crash anymore
```

### Pattern 3: The Build Gate

Before claiming code is complete:

```bash
# Does it at least compile/parse?
python -m py_compile new_file.py
npm run build
cargo check
```

### Pattern 4: The Integration Smell Test

After changes that affect multiple components:

```bash
# Start the service
npm run dev &

# Hit the affected endpoint
curl http://localhost:3000/affected-route

# Check for expected response
```

## The Verification Checklist

Before declaring done:

```
[ ] Code runs without syntax errors
[ ] Function produces expected output on happy path
[ ] Edge case handled (empty, null, boundary)
[ ] Original bug/issue no longer reproduces
[ ] No new errors introduced (check logs)
[ ] Build passes (if applicable)
```

## NEVER

- Say "done" without running the code
- Assume it works because it looks right
- Skip verification because you're confident
- Claim a bug is fixed without reproducing it first
- Trust that generated code is correct
- Trust a subagent's self-reported success without checking its actual output
- Let pattern-matching substitute for proof

## ALWAYS

- Run new code at least once
- Test the specific thing that was broken
- Show verification output in your response
- Admit when you can't verify (and say why)
- Treat verification as required, not optional

## Examples

### Example 1: Bad (No Verification)

```
User: "Fix the divide by zero error"

*edits code to add check*

Done! Added a check for zero before dividing. The function now returns
None if the divisor is zero.
```

This is a lie. I didn't verify anything.

### Example 1: Good (With Verification)

```
User: "Fix the divide by zero error"

*edits code to add check*

Let me verify the fix:

$ python -c "from math_utils import safe_divide; print(safe_divide(10, 0))"
None

$ python -c "from math_utils import safe_divide; print(safe_divide(10, 2))"
5.0

Verified:
- Division by zero returns None (was: crashed)
- Normal division still works
- Fix confirmed.
```

### Example 2: Admitting Inability To Verify

```
User: "Update the production config"

I've updated config/production.json with the new API endpoint.

Verification status: UNABLE TO VERIFY
- This is production config
- I can't safely test against production
- Recommend: Test in staging first, or have ops verify after deploy

Change is made but unverified. Proceed with caution.
```

### Example 3: Build Verification

```
User: "Add TypeScript types to the utils"

*adds types*

Verifying:

$ npm run typecheck
src/utils.ts - 0 errors

$ npm run build
Build successful - dist/utils.js generated

Verified: Types compile without errors, build passes.
```

<failed-attempts>
What DOESN'T work:

- **"I'll verify later"**: Later never comes. Verify immediately or it won't happen.
- **"It looks right"**: Pattern-matching is not verification. Code that looks perfect can be completely wrong.
- **"The tests will catch it"**: Tests you haven't run don't catch anything. Run them.
- **"It's a small change"**: Small changes cause big breaks. One-character typos crash production.
- **Verifying only the happy path**: The bug is in the edge case you didn't test.
- **Reading the code as verification**: Reading is not running. Execute it.
- **"It worked before"**: Before is not now. Dependencies change. Environments differ.
- **Trusting the type checker**: Types compile doesn't mean logic is correct.
- **"The agent reported success"**: Agent self-reports are not verification. Check its actual diff/output.
</failed-attempts>

## Rationalization Table (from superpowers verification-before-completion)

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler/tests |
| "Agent said success" | Verify independently — check the diff |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |

## The Hard Truth

When I say "Done!" without verifying, I'm not reporting a fact. I'm making a
prediction based on pattern-matching. Sometimes that prediction is wrong.

Verification converts prediction into observation. It's the difference between
"this should work" and "this works."

One is a guess. One is proof.

Prove it.

## Drive the real flow, not just tests
For a change with a runtime surface, "tests pass" is NOT proof — exercise the
ACTUAL affected flow and observe behavior: start the daemon and watch it import,
hit the endpoint, run the CLI on a real input, restart the service and confirm
it's active. Typical pipeline bugs (dead AutoRun path, wrong service ExecStart)
all passed a syntax check and only surfaced when the flow was actually driven.
The built-in `/verify` command is the heavier version of this for app flows.

## Hard rule — no "done" without fresh proof

- Run the proving command fresh in the same message as the claim; cite the output. A prior run, a subagent report, or "looks right" is not proof.
- Scope the claim to exactly what was verified; name what was not.
- "Prevented / stopped" claims need a durable artifact (`systemctl is-enabled`, `crontab -l`, `apt-mark showhold`, the config file), not one fixed symptom.
- A manifest of N similar assets means checking every one. 2 of 6 is a miss.
- High stakes (customer-facing, money, cron-exposed): run a second adversarial check before claiming done.
