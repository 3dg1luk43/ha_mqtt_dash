#!/usr/bin/env bash
# Build the profile editor (editor/) for the integration's HA panel and copy the
# bundle into custom_components/ha_mqtt_dash/editor/. The bundle IS committed:
# it is what HACS users download. Rebuild and commit it with the source change.
#
#   tools/build_editor.sh          build + copy + write build-manifest.json
#   tools/build_editor.sh --check  only verify the committed bundle matches the
#                                  current editor sources (no npm; used by CI)
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="custom_components/ha_mqtt_dash/editor"
WANT="$(python3 tools/editor_hash.py)"

if [[ "${1:-}" == "--check" ]]; then
  HAVE="$(python3 -c "import json,sys; print(json.load(open('$DEST/build-manifest.json')).get('source_hash',''))" 2>/dev/null || true)"
  if [[ "$WANT" == "$HAVE" && -f "$DEST/index.html" ]]; then
    echo "editor bundle is up to date"
    exit 0
  fi
  echo "editor bundle is STALE (built from ${HAVE:-nothing}, sources are $WANT) -> run tools/build_editor.sh and commit $DEST" >&2
  exit 1
fi

command -v npm >/dev/null || { echo "build_editor: npm is required" >&2; exit 1; }
( cd editor && { [[ -d node_modules ]] || npm ci --no-audit --no-fund; } && npm run --silent build:ha )
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R editor/dist-ha/. "$DEST/"
printf '{\n  "source_hash": "%s"\n}\n' "$WANT" > "$DEST/build-manifest.json"
echo "build_editor: bundle written to $DEST ($(du -sh "$DEST" | cut -f1))"
