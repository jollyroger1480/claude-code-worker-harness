#!/usr/bin/env bash
# install.sh: install the worker harness into your Claude Code config.
#
#   ./install.sh               install (or update) everything
#   ./install.sh --dry-run     print what would happen, change nothing
#   ./install.sh --uninstall   remove what this script installed and restore backups
#   ./install.sh --no-settings do not touch settings.json (merge settings.example.json by hand)
#   ./install.sh --no-grok-lane  skip bin/grok-leaf
#
# Where things go:
#   agents  -> $CFG/agents/<name>.md
#   hooks   -> $CFG/hooks/claude-harness/
#   skills  -> $CFG/skills/<name>/
#   bin     -> ${HARNESS_BIN_DIR:-$HOME/.local/bin}/grok-leaf
# with CFG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}.
#
# Safety: an existing file that differs is moved to <file>.bak.<timestamp> before it is
# replaced, and the move is recorded in $CFG/claude-harness/manifest.tsv. Running the
# script twice is safe: identical files are skipped, hook entries are added only once.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
BIN="${HARNESS_BIN_DIR:-$HOME/.local/bin}"
STATE="$CFG/claude-harness"
MANIFEST="$STATE/manifest.tsv"
stamp="$(date +%Y%m%d-%H%M%S)"

dry=0; uninstall=0; settings=1; grok=1
for a in "$@"; do
  case "$a" in
    --dry-run) dry=1 ;;
    --uninstall) uninstall=1 ;;
    --no-settings) settings=0 ;;
    --no-grok-lane) grok=0 ;;
    -h|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "install.sh: unknown option $a" >&2; exit 2 ;;
  esac
done

say() { if [ "$dry" -eq 1 ]; then echo "[dry-run] $*"; else echo "$*"; fi; }
run() { if [ "$dry" -eq 0 ]; then "$@"; fi; }

command -v python3 >/dev/null || { echo "install.sh: python3 is required" >&2; exit 1; }

merge_settings() {  # $1 = add | remove
  local mode="$1" file="$CFG/settings.json"
  if [ "$settings" -eq 0 ]; then say "skip settings.json (--no-settings)"; return; fi
  if [ -f "$file" ] && python3 -I "$here/lib/settings_merge.py" "$mode" "$file" "$here/settings.example.json" --check | grep -q 'would'; then
    say "backup  $file -> $file.bak.$stamp"
    run cp -p -- "$file" "$file.bak.$stamp"
  fi
  if [ "$dry" -eq 1 ]; then
    python3 -I "$here/lib/settings_merge.py" "$mode" "$file" "$here/settings.example.json" --check
  else
    python3 -I "$here/lib/settings_merge.py" "$mode" "$file" "$here/settings.example.json"
  fi
}

place() {  # $1 = source file, $2 = destination
  local src="$1" dst="$2" bak=""
  if [ -e "$dst" ] && cmp -s -- "$src" "$dst"; then
    say "same    $dst"
    return
  fi
  if [ -e "$dst" ]; then
    bak="$dst.bak.$stamp"
    say "backup  $dst -> $bak"
    run mv -- "$dst" "$bak"
  fi
  say "install $dst"
  run mkdir -p -- "$(dirname -- "$dst")"
  run cp -p -- "$src" "$dst"
  if [ "$dry" -eq 0 ]; then printf '%s\t%s\n' "$dst" "$bak" >> "$MANIFEST"; fi
}

if [ "$uninstall" -eq 1 ]; then
  if [ ! -f "$MANIFEST" ]; then echo "Nothing to uninstall: $MANIFEST not found."; exit 0; fi
  # Newest entries first, so a file installed twice ends with its oldest backup restored.
  tac -- "$MANIFEST" | while IFS=$'\t' read -r dst bak; do
    [ -n "$dst" ] || continue
    if [ -e "$dst" ]; then say "remove  $dst"; run rm -f -- "$dst"; fi
    if [ -n "$bak" ] && [ -e "$bak" ]; then say "restore $bak -> $dst"; run mv -- "$bak" "$dst"; fi
  done
  merge_settings remove
  for d in "$CFG/hooks/claude-harness/model-router" "$CFG/hooks/claude-harness/guards" "$CFG/hooks/claude-harness"; do
    [ -d "$d" ] && run rmdir --ignore-fail-on-non-empty -- "$d"
  done
  say "remove  $MANIFEST"
  run rm -f -- "$MANIFEST"
  run rmdir --ignore-fail-on-non-empty -- "$STATE" 2>/dev/null || true
  echo "Uninstalled. Skill folders left empty by the removal can be deleted by hand."
  exit 0
fi

say "config dir: $CFG"
run mkdir -p -- "$STATE"

for f in "$here"/agents/*.md; do place "$f" "$CFG/agents/$(basename -- "$f")"; done
for f in "$here"/hooks/model-router/* "$here"/hooks/guards/*; do
  [ -f "$f" ] || continue
  rel="${f#"$here/hooks/"}"
  place "$f" "$CFG/hooks/claude-harness/$rel"
done
while IFS= read -r -d '' f; do
  rel="${f#"$here/skills/"}"
  place "$f" "$CFG/skills/$rel"
done < <(find "$here/skills" -type f ! -name '*.pyc' -print0 | sort -z)
if [ "$grok" -eq 1 ]; then place "$here/bin/grok-leaf" "$BIN/grok-leaf"; fi

merge_settings add

if [ "$dry" -eq 0 ]; then
  echo
  echo "Done. Next steps:"
  echo "  1. Edit the model: lines in $CFG/agents/*.md to model ids your account offers."
  echo "  2. Start a new Claude Code session (hooks load at start)."
  case ":$PATH:" in *":$BIN:"*) ;; *) [ "$grok" -eq 1 ] && echo "  3. Add $BIN to PATH to use grok-leaf." ;; esac
fi
