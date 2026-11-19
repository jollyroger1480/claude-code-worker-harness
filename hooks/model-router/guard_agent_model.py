#!/usr/bin/env python3
"""PreToolUse hook: send each sub-agent to the named worker from the post.

The model id is pinned in agents/<name>.md under the Claude config dir. This hook sets
subagent_type and strips model, because a versioned model id on the Agent
tool call is rejected. An unspecified general-purpose spawn goes to
the read worker (routine-worker) unless the prompt contains OPUS-REASON:. Built-in types (Explore, Plan, fork,
claude-code-guide, statusline-setup, web-fetch) pass through untouched. The tier is read from
the description and the top of the prompt first, and hard-thinking work (solve,
debug, investigate, audit ...) is never sent to the read or lookup worker.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from router_lib import (
    PASSTHROUGH,
    classify,
    has_reason,
    is_expensive,
    load_routing,
    task_head,
    task_text,
    worker_name,
)

AGENT_TOOLS = {"Agent", "Task"}
CHEAP = {"read", "lookup"}


def emit(decision: str, reason: str, updated: dict | None = None, note: str = "") -> None:
    specific = {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }
    if updated is not None:
        specific["updatedInput"] = updated
    if note:
        specific["additionalContext"] = note
    json.dump({"hookSpecificOutput": specific}, sys.stdout)
    sys.stdout.write("\n")


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    payload = json.loads(raw)
    if payload.get("tool_name") not in AGENT_TOOLS:
        return 0

    routing = load_routing()
    tool_input = dict(payload.get("tool_input") or {})
    text = task_text(tool_input)
    subagent_type = str(tool_input.get("subagent_type") or "")
    model = str(tool_input.get("model") or "").strip()
    if subagent_type in PASSTHROUGH:
        return 0
    tier = classify(text, subagent_type, routing, task_head(tool_input))
    token = routing.get("reason_token") or "OPUS-REASON:"

    if tier == "outsource" or subagent_type == "lowtier":
        emit(
            "deny",
            "Odd jobs go to the lowtier skill (the cheap lane), not a Claude sub-agent.",
        )
        return 0

    if tier == "review" or subagent_type in {"code-reviewer", "security-reviewer"}:
        emit(
            "deny",
            "Code review uses Alibaba Open Code Review, not a Claude sub-agent. "
            "On a git diff run `ocr review --audience agent`. "
            "With no diff run `ocr scan --path <files> --audience agent`.",
        )
        return 0

    if tier in CHEAP and model and is_expensive(model, routing) and not has_reason(text, routing):
        emit(
            "deny",
            f"This is {tier} work. Use {worker_name(tier, text, subagent_type)}, not {model}. "
            f"If the expensive model is actually required, put {token} and one sentence in the prompt.",
        )
        return 0

    if has_reason(text, routing) and not tier:
        return 0

    if not tier:
        # No clear job type: send it to the read worker instead of refusing. A refusal
        # costs a full resend of the prompt. OPUS-REASON: (above) keeps it off the cheap worker.
        tier = "read"

    name = worker_name(tier, text, subagent_type) or subagent_type
    if not name:
        return 0

    updated = dict(tool_input)
    updated.pop("model", None)
    updated["subagent_type"] = name
    if updated == tool_input:
        return 0

    emit(
        "allow",
        f"Assigned {name} for {tier}. The model id is on that agent file.",
        updated,
        f"model-router set this sub-agent to {name} ({tier}).",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"model-router hook error: {exc}\n")
        raise SystemExit(0)
