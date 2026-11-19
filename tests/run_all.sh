#!/usr/bin/env bash
# ok() always succeeds, so "test && ok || bad" is safe here.
# shellcheck disable=SC2015
# Run every check in the repo. Touches nothing outside a throwaway temp folder.
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root" || exit 1
tmp="$(mktemp -d "${TMPDIR:-/tmp}/harness-tests.XXXXXX")"
trap 'rm -rf -- "$tmp"' EXIT
export PYTHONDONTWRITEBYTECODE=1
fails=0
step() { printf '\n== %s\n' "$1"; }
ok() { echo "ok: $1"; }
bad() { echo "FAIL: $1"; fails=$((fails + 1)); }

step "python byte-compile"
while IFS= read -r -d '' f; do
  if python3 -I -c 'import ast,sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' "$f"; then ok "$f"; else bad "$f"; fi
done < <(find . -name '*.py' -not -path './.git/*' -print0 | sort -z)

step "json"
for f in settings.example.json hooks/model-router/routing.json; do
  if python3 -I -m json.tool "$f" >/dev/null; then ok "$f"; else bad "$f"; fi
done

step "router and guard tests"
if python3 -I tests/test_router.py 2>&1 | tail -3; then ok "unittest"; else bad "unittest"; fi

step "shell syntax"
for f in install.sh bin/grok-leaf tests/run_all.sh; do
  if bash -n "$f"; then ok "bash -n $f"; else bad "bash -n $f"; fi
done
if command -v shellcheck >/dev/null; then
  if shellcheck install.sh bin/grok-leaf tests/run_all.sh; then ok "shellcheck"; else bad "shellcheck"; fi
else
  echo "skip: shellcheck not installed"
fi

step "install.sh in a temp HOME"
h="$tmp/home"; mkdir -p "$h/.claude/agents"
printf '{"theme":"dark","hooks":{"Stop":[{"hooks":[{"type":"command","command":"true"}]}]}}\n' > "$h/.claude/settings.json"
echo "my own architect" > "$h/.claude/agents/architect.md"
before="$(find "$h" -type f | wc -l)"
HOME="$h" CLAUDE_CONFIG_DIR='' HARNESS_BIN_DIR="$h/bin" ./install.sh --dry-run >/dev/null || bad "dry-run exit code"
[ "$(find "$h" -type f | wc -l)" -eq "$before" ] && ok "dry-run changed nothing" || bad "dry-run wrote files"
HOME="$h" CLAUDE_CONFIG_DIR='' HARNESS_BIN_DIR="$h/bin" ./install.sh >/dev/null || bad "install exit code"
n_hooks() { python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sum(len(g["hooks"]) for v in d.get("hooks",{}).values() for g in v))' "$h/.claude/settings.json"; }
[ "$(n_hooks)" -eq 4 ] && ok "3 hooks added next to the existing one" || bad "hook count after install: $(n_hooks)"
[ -x "$h/bin/grok-leaf" ] && ok "grok-leaf installed" || bad "grok-leaf missing"
ls "$h/.claude/agents/"architect.md.bak.* >/dev/null 2>&1 && ok "existing agent backed up" || bad "no backup of existing agent"
out="$(HOME="$h" CLAUDE_CONFIG_DIR='' HARNESS_BIN_DIR="$h/bin" ./install.sh)"
echo "$out" | grep -q '^install ' && bad "second run reinstalled files" || ok "second run is a no-op"
[ "$(n_hooks)" -eq 4 ] && ok "no duplicate hooks" || bad "hook count after rerun: $(n_hooks)"
# The installed hooks must run from their installed location.
echo '{"tool_name":"Agent","tool_input":{"description":"read the log","prompt":"read x","subagent_type":"general-purpose"}}' \
  | HOME="$h" MODEL_ROUTER_STATE_DIR="$tmp/state" python3 "$h/.claude/hooks/claude-harness/model-router/guard_agent_model.py" \
  | grep -q routine-worker && ok "installed guard routes to routine-worker" || bad "installed guard did not route"
HOME="$h" CLAUDE_CONFIG_DIR='' HARNESS_BIN_DIR="$h/bin" ./install.sh --uninstall >/dev/null || bad "uninstall exit code"
[ "$(cat "$h/.claude/agents/architect.md")" = "my own architect" ] && ok "backup restored" || bad "backup not restored"
[ "$(n_hooks)" -eq 1 ] && ok "only the user's own hook remains" || bad "hook count after uninstall: $(n_hooks)"
python3 -I -c 'import json,sys; assert json.load(open(sys.argv[1]))["theme"]=="dark"' "$h/.claude/settings.json" \
  && ok "other settings kept" || bad "other settings lost"
[ ! -e "$h/bin/grok-leaf" ] && ok "grok-leaf removed" || bad "grok-leaf left behind"

step "grok-leaf without grok"
env -i HOME="$tmp/nohome" PATH=/usr/bin:/bin bin/grok-leaf "hello" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 3 ] && ok "exit 3 when grok is missing" || bad "expected exit 3, got $rc"
bin/grok-leaf --always-approve hi >/dev/null 2>&1; rc=$?
[ "$rc" -eq 2 ] && ok "refuses --always-approve" || bad "expected exit 2, got $rc"
fake="sk-$(printf 'x%.0s' $(seq 1 24))"
CHEAP_LEAF_CMD='cat' bin/grok-leaf "key $fake" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 4 ] && ok "refuses a prompt with a key in it" || bad "expected exit 4, got $rc"
[ "$(CHEAP_LEAF_CMD='tr a-z A-Z' bin/grok-leaf 'adapter works')" = "ADAPTER WORKS" ] \
  && ok "CHEAP_LEAF_CMD adapter" || bad "adapter output wrong"

echo
if [ "$fails" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "$fails CHECK(S) FAILED"; fi
exit "$fails"
