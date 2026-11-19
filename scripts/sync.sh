#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DST="${MILESTONE_PLUGIN_DIR:-$HOME/.gemini/config/plugins/milestone-progress}"

FILES=(
  "plugin.json"
  "hooks.json"
  "rules/AGENTS.md"
  "skills/milestone-mode/SKILL.md"
  "hooks/progress_hook.py"
)

echo "==> 1/3 Running unit tests..."
python3 "$SRC/tests/test_progress_hook.py" -v

echo "==> 2/3 Syncing plugin files to $DST..."
for rel in "${FILES[@]}"; do
  mkdir -p "$DST/$(dirname "$rel")"
  cp "$SRC/$rel" "$DST/$rel"
done

echo "==> 3/3 Verifying sync..."
for rel in "${FILES[@]}"; do
  diff -q "$SRC/$rel" "$DST/$rel" >/dev/null
  echo "  OK: $rel"
done

VERSION="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$SRC/plugin.json")"
echo "Done: milestone-progress v$VERSION synced and verified."
