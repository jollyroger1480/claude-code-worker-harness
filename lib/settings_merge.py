#!/usr/bin/env python3
"""Add or remove this harness's hook entries in a Claude Code settings.json.

    settings_merge.py add    SETTINGS EXAMPLE [--check]
    settings_merge.py remove SETTINGS EXAMPLE [--check]

Only the "hooks" block of EXAMPLE is used; permissions are never touched.
A hook entry is identified by its command string, so running "add" twice adds
nothing the second time, and "remove" deletes only entries whose command points
at hooks/claude-harness/. With --check nothing is written; the planned change
is printed instead. Other keys and other hooks in SETTINGS are left as they are.
"""
import json
import os
import sys
import tempfile

MARK = "hooks/claude-harness/"


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    return json.loads(text) if text else {}


def commands(group):
    return {h.get("command") for h in group.get("hooks", []) if isinstance(h, dict)}


def add(settings, example):
    added = []
    hooks = settings.setdefault("hooks", {})
    for event, groups in example.get("hooks", {}).items():
        have = hooks.setdefault(event, [])
        existing = set().union(*(commands(g) for g in have)) if have else set()
        for group in groups:
            if commands(group) <= existing:
                continue
            have.append(group)
            added.append(f"{event} [{group.get('matcher', '*')}]")
    return added


def remove(settings):
    removed = []
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        kept = []
        for group in hooks[event]:
            inner = [h for h in group.get("hooks", []) if MARK not in str(h.get("command", ""))]
            if len(inner) != len(group.get("hooks", [])):
                removed.append(f"{event} [{group.get('matcher', '*')}]")
            if inner:
                group["hooks"] = inner
                kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks and "hooks" in settings:
        del settings["hooks"]
    return removed


def main(argv):
    args = [a for a in argv if a != "--check"]
    check = "--check" in argv
    if len(args) != 3 or args[0] not in ("add", "remove"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    mode, path, example_path = args
    try:
        settings = load(path)
    except json.JSONDecodeError as exc:
        print(f"settings_merge: {path} is not valid JSON ({exc}); not touching it.", file=sys.stderr)
        return 1
    changes = add(settings, load(example_path)) if mode == "add" else remove(settings)
    verb = "would " if check else ""
    if not changes:
        print(f"settings.json: nothing to {mode}")
        return 0
    for c in changes:
        print(f"settings.json: {verb}{mode} hook {c}")
    if check:
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
