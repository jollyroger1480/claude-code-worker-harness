"""Shared routing rules for the model-router hooks.

The workflow list in routing.json is the post's table, in that order.
This assigns a model. It does not rewrite prompts, and it does not try to
get a model past a refusal.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _routing_path() -> Path:
    """routing.json next to the hooks (installed layout), or MODEL_ROUTER_CONFIG."""
    override = os.environ.get("MODEL_ROUTER_CONFIG")
    if override:
        return Path(override)
    return HERE / "routing.json"


ROUTING_PATH = _routing_path()

# Same order as the table: execution, architect, code/security review, read, lookup.
# A design or plan review stays on architect. It is not a code review.
EXEC_RE = re.compile(
    r"\b(implement|write the code|fix the bug|edit the file|refactor|patch)\b",
    re.I,
)
ARCH_RE = re.compile(
    r"\b(architect|architecture|design|schema|trade-?off|system plan|technical plan)\b",
    re.I,
)
REVIEW_RE = re.compile(
    r"\b(code review|security review|review (?:this|the) (?:code|diff|patch|pr|pull request))\b",
    re.I,
)
READ_RE = re.compile(
    r"\b(read|summarize|summary|document|docs|markdown|\.md\b|pdf|pages?)\b",
    re.I,
)
LOOKUP_RE = re.compile(
    r"\b(status|grep|rg\b|find|where is|list files|look up|lookup|search the)\b",
    re.I,
)
# Work that needs real thinking. It never goes to the read or lookup worker, even when
# the prompt also says "read" or "find" (a long prompt nearly always does).
HARD_RE = re.compile(
    r"\b(solve|from scratch|prove|derive|debug|root cause|investigate|audit|analy[sz]e|"
    r"second opinion|independent(?:ly)? review|reason (?:about|through)|cryptanaly\w*)\b",
    re.I,
)
# Built-in agent types that already have their own model and tools. The router leaves
# them alone: rewriting a fork drops its inherited context, and Explore is already cheap.
# web-fetch is sandboxed to WebFetch only; rerouting it would hand untrusted page text
# to a worker with every tool.
PASSTHROUGH = {"Explore", "Plan", "fork", "claude-code-guide", "statusline-setup", "web-fetch"}
# The job is stated at the top of a prompt. Keywords further down are background.
HEAD_CHARS = 400


def load_routing() -> dict:
    with ROUTING_PATH.open() as fh:
        return json.load(fh)


def workflow(routing: dict) -> list[dict]:
    return list(routing.get("workflow") or [])


def tier_model(tier: str, routing: dict) -> str:
    for row in workflow(routing):
        if row.get("role") == tier:
            return str(row.get("model") or "")
    return ""


def main_model(routing: dict) -> str:
    for row in workflow(routing):
        if row.get("where") == "main":
            return str(row.get("model") or "")
    return ""


def keyword_tier(blob: str) -> str | None:
    if EXEC_RE.search(blob):
        return "execution"
    if ARCH_RE.search(blob):
        return "architect"
    if REVIEW_RE.search(blob):
        return "review"
    if READ_RE.search(blob):
        return "read"
    if LOOKUP_RE.search(blob):
        return "lookup"
    return None


def classify(text: str, subagent_type: str, routing: dict, head: str = "") -> str | None:
    if subagent_type == "lowtier":
        return "outsource"
    for row in workflow(routing):
        if subagent_type and subagent_type in (row.get("subagent_types") or []):
            return str(row.get("role") or "")
    blob = text or ""
    tier = keyword_tier(head) if head else None
    if tier is None:
        tier = keyword_tier(blob)
    if tier in (None, "read", "lookup") and HARD_RE.search(blob):
        return "execution"
    return tier


def worker_name(tier: str, text: str = "", subagent_type: str = "") -> str:
    if subagent_type in {
        "opus-worker",
        "architect",
        "code-reviewer",
        "security-reviewer",
        "routine-worker",
        "quick-worker",
    }:
        return subagent_type
    if tier == "execution":
        return "opus-worker"
    if tier == "architect":
        return "architect"
    if tier == "review":
        if "security" in (text or "").lower():
            return "security-reviewer"
        return "code-reviewer"
    if tier == "read":
        return "routine-worker"
    if tier == "lookup":
        return "quick-worker"
    return ""


def is_expensive(model: str, routing: dict) -> bool:
    folded = (model or "").lower()
    return any(marker in folded for marker in routing.get("expensive_markers") or [])


def has_reason(text: str, routing: dict) -> bool:
    token = routing.get("reason_token") or "OPUS-REASON:"
    return token in (text or "")


def task_text(tool_input: dict) -> str:
    parts = []
    for key in ("prompt", "description", "name", "subagent_type"):
        value = tool_input.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def task_head(tool_input: dict) -> str:
    """The short description plus the opening of the prompt: where the job is stated."""
    parts = []
    for key in ("description", "name"):
        value = tool_input.get(key)
        if isinstance(value, str):
            parts.append(value)
    prompt = tool_input.get("prompt")
    if isinstance(prompt, str):
        parts.append(prompt[:HEAD_CHARS])
    return "\n".join(parts)


def estimate_tokens(transcript_path: str) -> int | None:
    """Tokens in the live context. Uses the usage block of the last API turn in the
    transcript (input + cache read + cache write). The file itself keeps everything
    from before each compaction, so its size is not the context size. Falls back to
    bytes / 4 when no usage block is found."""
    if not transcript_path:
        return None
    path = Path(transcript_path)
    if not path.is_file():
        return None
    size = path.stat().st_size
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, size - 2_000_000))
            tail = handle.read().decode("utf-8", "replace")
        for line in reversed(tail.splitlines()):
            if '"usage"' not in line:
                continue
            try:
                usage = (json.loads(line).get("message") or {}).get("usage") or {}
            except ValueError:
                continue
            total = sum(
                int(usage.get(key) or 0)
                for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
            )
            if total:
                return total
    except OSError:
        pass
    # bytes / 4 only when the whole file was searched. A tail-only search that found
    # no usage block says nothing about live context, so stay quiet (None).
    return size // 4 if size <= 2_000_000 else None
