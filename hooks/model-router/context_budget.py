#!/usr/bin/env python3
"""UserPromptSubmit hook: three steps set in routing.json: from context_delegate_tokens
it tells Claude to hand long reads to the cheap workers, from context_warn_tokens it
asks for a compact at the next break, and from 85% of context_limit_tokens it says
compact now.

Each step is said once per session, not on every prompt. It does not compact and it does not delete the transcript. It runs for
every project.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from router_lib import estimate_tokens, load_routing


STATE_DIR = Path(
    os.environ.get("MODEL_ROUTER_STATE_DIR")
    or Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "model-router"
)


def should_speak(session: str, step: int) -> bool:
    """Say each step once per session. A lower step (after a compact) resets it,
    so the next climb speaks again. Step 0 never speaks."""
    name = "".join(ch for ch in session if ch.isalnum() or ch in "-_")[-80:] or "unknown"
    path = STATE_DIR / f"{name}.step"
    try:
        last = int(path.read_text().strip())
    except (OSError, ValueError):
        last = 0
    if step != last:
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(str(step))
        except OSError:
            pass
    return step > last


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    payload = json.loads(raw)
    routing = load_routing()

    tokens = estimate_tokens(str(payload.get("transcript_path") or ""))
    if tokens is None:
        return 0

    delegate = int(routing.get("context_delegate_tokens") or 80000)
    warn = int(routing.get("context_warn_tokens") or 120000)
    limit = int(routing.get("context_limit_tokens") or 200000)
    hard = int(limit * 0.85)
    step = 3 if tokens >= hard else 2 if tokens >= warn else 1 if tokens >= delegate else 0
    if not should_speak(str(payload.get("session_id") or payload.get("transcript_path") or ""), step):
        return 0

    line = (
        f"model-router: context is about {tokens} of {limit} tokens. "
        "Hand long reads, searches, logs and file dumps to quick-worker or routine-worker "
        "and keep only their conclusions in this thread."
    )
    if tokens >= hard:
        line += (
            " Compact NOW: tell the user to run /compact before any other work, "
            "and do not start a long read or a multi-step job in this thread."
        )
    elif tokens >= warn:
        line += " Compact at the next natural break (ask the user to run /compact)."
    out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": line}}
    if tokens >= warn:
        out["systemMessage"] = line
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"model-router budget error: {exc}\n")
        raise SystemExit(0)
