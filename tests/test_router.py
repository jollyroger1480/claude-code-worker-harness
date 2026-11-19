#!/usr/bin/env python3
"""Stdin tests for the model router. No Claude process."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks" / "model-router"
GUARD = HOOKS / "guard_agent_model.py"
BUDGET = HOOKS / "context_budget.py"
WAITLOOP = ROOT / "hooks" / "guards" / "no-self-matching-wait-loops.py"
sys.path.insert(0, str(HOOKS))

# Hooks write their once-per-session state here, never in the real home.
STATE = tempfile.mkdtemp(prefix="model-router-test-")

from router_lib import load_routing, workflow  # noqa: E402

POST_ORDER = (
    "commander",
    "execution",
    "architect",
    "review",
    "read",
    "lookup",
    "outsource",
)


def run_hook(script: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, MODEL_ROUTER_STATE_DIR=STATE, HOME=STATE)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def decision(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)["hookSpecificOutput"]


class WorkflowTests(unittest.TestCase):
    def test_table_order_matches_the_post(self) -> None:
        rows = workflow(load_routing())
        self.assertEqual(tuple(row["role"] for row in rows), POST_ORDER)
        models = {row["role"]: row.get("model") for row in rows}
        self.assertEqual(models["commander"], "claude-mythos-5-2")
        self.assertEqual(models["execution"], "claude-opus-5-5")
        self.assertEqual(models["architect"], "claude-fable-5-2")
        self.assertEqual(models["review"], "")
        self.assertEqual(rows[3]["tool"], "ocr")
        self.assertEqual(models["read"], "claude-sonnet-5-5")
        self.assertEqual(models["lookup"], "claude-haiku-5-5")
        self.assertEqual(models["outsource"], "")
        self.assertIn("2122212822138650873", load_routing()["post"])


class GuardTests(unittest.TestCase):
    def test_any_project_still_gets_a_worker(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/srv/shop/scripts",
                "tool_input": {"prompt": "read the listing file"},
            },
        )
        updated = decision(result)["updatedInput"]
        self.assertEqual(updated["subagent_type"], "routine-worker")
        self.assertNotIn("model", updated)

    def test_read_is_assigned_the_named_worker(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {
                    "prompt": "read the markdown doc and summarize it",
                    "model": "claude-sonnet-5-5",
                },
            },
        )
        updated = decision(result)["updatedInput"]
        self.assertEqual(updated["subagent_type"], "routine-worker")
        self.assertNotIn("model", updated)

    def test_execution_beats_a_design_word(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {"prompt": "implement the architecture in the schema"},
            },
        )
        self.assertEqual(decision(result)["updatedInput"]["subagent_type"], "opus-worker")

    def test_design_review_stays_on_architect(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {"prompt": "review the architecture and the technical plan"},
            },
        )
        self.assertEqual(decision(result)["updatedInput"]["subagent_type"], "architect")

    def test_code_review_uses_alibaba_ocr(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {
                    "subagent_type": "code-reviewer",
                    "prompt": "review this diff",
                    "model": "claude-opus-4-6",
                },
            },
        )
        specific = decision(result)
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("ocr review", specific["permissionDecisionReason"])

    def test_opus_on_a_lookup_is_denied(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Task",
                "cwd": "/tmp",
                "tool_input": {
                    "prompt": "grep the repo and tell me where the config is",
                    "model": "claude-opus-5-5",
                },
            },
        )
        specific = decision(result)
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("quick-worker", specific["permissionDecisionReason"])

    def test_opus_reason_keeps_an_unspecified_spawn(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {
                    "prompt": "do the thing. OPUS-REASON: this one stays on the main worker.",
                    "subagent_type": "general-purpose",
                },
            },
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_unspecified_spawn_goes_to_the_read_worker(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {"prompt": "do the thing", "subagent_type": "general-purpose"},
            },
        )
        self.assertEqual(decision(result)["permissionDecision"], "allow")
        self.assertEqual(decision(result)["updatedInput"]["subagent_type"], "routine-worker")

    def test_named_worker_is_left_alone(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {"subagent_type": "quick-worker", "prompt": "check status"},
            },
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_lowtier_is_the_skill_not_a_claude_agent(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {"subagent_type": "lowtier", "prompt": "draft a blurb"},
            },
        )
        self.assertEqual(decision(result)["permissionDecision"], "deny")
        self.assertIn("lowtier", decision(result)["permissionDecisionReason"])

    def test_hard_thinking_never_goes_to_the_read_worker(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {
                    "subagent_type": "general-purpose",
                    "description": "Independent puzzle review",
                    "prompt": "Solve puzzle 1 from scratch. Read the status file first, read-only.",
                },
            },
        )
        self.assertEqual(decision(result)["updatedInput"]["subagent_type"], "opus-worker")

    def test_builtin_types_pass_through(self) -> None:
        for kind in ("Explore", "Plan", "fork", "claude-code-guide", "web-fetch"):
            result = run_hook(
                GUARD,
                {
                    "tool_name": "Agent",
                    "cwd": "/tmp",
                    "tool_input": {"subagent_type": kind, "prompt": "read the docs and find the flag"},
                },
            )
            self.assertEqual(result.stdout.strip(), "", kind)

    def test_head_of_prompt_beats_a_late_keyword(self) -> None:
        result = run_hook(
            GUARD,
            {
                "tool_name": "Agent",
                "cwd": "/tmp",
                "tool_input": {
                    "description": "Where is the port set",
                    "prompt": "grep the repo for the port. " + "x " * 300 + "the design doc may mention it",
                },
            },
        )
        self.assertEqual(decision(result)["updatedInput"]["subagent_type"], "quick-worker")


def usage_file(tmp, tokens: int) -> None:
    tmp.write(json.dumps({"message": {"usage": {"input_tokens": tokens}}}).encode() + b"\n")
    tmp.flush()


class BudgetTests(unittest.TestCase):
    def test_three_steps(self) -> None:
        seen = {}
        for tokens in (100000, 130000, 160000, 180000):
            with tempfile.NamedTemporaryFile() as tmp:
                usage_file(tmp, tokens)
                result = run_hook(BUDGET, {"cwd": "/tmp", "transcript_path": tmp.name, "prompt": "hi"})
            seen[tokens] = result.stdout.strip()
        self.assertEqual(seen[100000], "")
        step1 = json.loads(seen[130000])
        self.assertIn("quick-worker", step1["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("Compact", step1["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("systemMessage", step1)
        self.assertIn("next natural break", json.loads(seen[160000])["systemMessage"])
        self.assertIn("Compact NOW", json.loads(seen[180000])["systemMessage"])

    def test_each_step_is_said_once(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            usage_file(tmp, 160000)
            payload = {"cwd": "/tmp", "transcript_path": tmp.name, "prompt": "hi"}
            first = run_hook(BUDGET, payload)
            second = run_hook(BUDGET, payload)
        self.assertIn("next natural break", first.stdout)
        self.assertEqual(second.stdout.strip(), "")

    def test_small_transcript_is_quiet(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b"x" * 100)
            tmp.flush()
            result = run_hook(
                BUDGET,
                {"cwd": "/tmp", "transcript_path": tmp.name, "prompt": "hi"},
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_large_transcript_warns(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b"x" * (200000 * 4))
            tmp.flush()
            result = run_hook(
                BUDGET,
                {"cwd": "/srv/shop", "transcript_path": tmp.name, "prompt": "hi"},
            )
        self.assertIn("Compact", decision(result)["additionalContext"])

    def test_usage_block_beats_file_size(self) -> None:
        line = json.dumps({"message": {"usage": {"input_tokens": 5, "cache_read_input_tokens": 40000}}})
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b"x" * (400000 * 4) + b"\n" + line.encode() + b"\n")
            tmp.flush()
            result = run_hook(
                BUDGET,
                {"cwd": "/tmp", "transcript_path": tmp.name, "prompt": "hi"},
            )
        self.assertEqual(result.stdout.strip(), "")

    def test_usage_outside_tail_window_stays_quiet(self) -> None:
        # Last usage block sits before the 2MB tail (a huge tool result after it):
        # the file size is not live context, so the hook must not demand a compact.
        line = json.dumps({"message": {"usage": {"input_tokens": 40000}}})
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(line.encode() + b"\n" + b"x" * 3_000_000 + b"\n")
            tmp.flush()
            result = run_hook(
                BUDGET,
                {"cwd": "/tmp", "transcript_path": tmp.name, "prompt": "hi"},
            )
        self.assertEqual(result.stdout.strip(), "")


class GuardEdgeTests(unittest.TestCase):
    def test_non_agent_tool_is_ignored(self) -> None:
        result = run_hook(GUARD, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual((result.returncode, result.stdout.strip()), (0, ""))

    def test_bad_json_never_blocks(self) -> None:
        for script in (GUARD, BUDGET):
            result = subprocess.run(
                [sys.executable, str(script)], input="{not json", text=True,
                capture_output=True, check=False,
                env=dict(os.environ, MODEL_ROUTER_STATE_DIR=STATE, HOME=STATE),
            )
            self.assertEqual(result.returncode, 0, script.name)
            self.assertEqual(result.stdout.strip(), "", script.name)


PG = "pg" + "rep"  # kept split so this file never trips the guard it tests


class WaitLoopGuardTests(unittest.TestCase):
    def run_cmd(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", str(WAITLOOP)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
            text=True, capture_output=True, check=False,
        )

    def test_self_matching_loop_is_blocked(self) -> None:
        result = self.run_cmd(f"until ! {PG} -f myjob; do sleep 5; done")
        self.assertEqual(result.returncode, 2)
        self.assertIn("matches", result.stderr)

    def test_bracket_pattern_is_allowed(self) -> None:
        self.assertEqual(self.run_cmd(f"while {PG} -f '[m]yjob'; do sleep 5; done").returncode, 0)

    def test_plain_command_is_allowed(self) -> None:
        self.assertEqual(self.run_cmd("ls -la").returncode, 0)

    def test_bad_input_is_allowed(self) -> None:
        result = subprocess.run([sys.executable, "-I", str(WAITLOOP)], input="nope",
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
