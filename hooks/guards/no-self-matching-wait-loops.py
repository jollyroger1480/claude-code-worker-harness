#!/usr/bin/env python3
"""PreToolUse(Bash): refuse wait loops that can never end.

`until ! pgrep -f "job"; do sleep N; done` matches its own shell, because
pgrep -f reads full command lines and the loop's command line holds the
pattern. Such loops can sit for hours after their jobs end.
"""
import json, re, sys

LOOP = re.compile(
    r"\b(?:until|while)\b[^;\n]*?\bpgrep\s+(?:-[A-Za-z]+\s+)*-[A-Za-z]*f[A-Za-z]*\s+"
    r"(?:-[A-Za-z]+\s+)*(\"[^\"]*\"|'[^']*'|\S+)"
)

def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    for m in LOOP.finditer(cmd):
        pattern = m.group(1)
        if "[" in pattern:      # bracket pattern cannot match its own shell
            continue
        sys.stderr.write(
            "Blocked: this wait loop uses `pgrep -f " + pattern + "`, which matches "
            "the loop's own shell, so it never ends and leaves a stuck shell.\n"
            "Use one of these instead:\n"
            "  - start the job with run_in_background and wait for its completion notice;\n"
            "  - wait on the PID: tail --pid=$PID -f /dev/null\n"
            "  - a pattern that cannot match itself, e.g. pgrep -f \"[m]yjob.py --flag\"\n"
        )
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
