#!/usr/bin/env bash
# Deploy FROM this repository TO the production Home Assistant (SMB mount).
# Modelled on ha_washdata's deploy_to_ha.sh. Dry-run unless --run is given.
#
#   tools/deploy_to_ha.sh                 show what would happen
#   tools/deploy_to_ha.sh --run           backup, rebuild editor, sync, restart HA
#   tools/deploy_to_ha.sh --run --editor  only the editor bundle (static files: no restart)
#
# Settings come from tools/deploy.env (gitignored; copy tools/deploy.env.example)
# or the environment:
#   HA_CONFIG          mounted HA config directory (e.g. an SMB/NFS mount of /config)
#   HA_URL             HA base URL for the restart call
#   HA_API_TOKEN_FILE  file holding a long-lived admin token (never put it in a script)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPONENT="ha_mqtt_dash"
# shellcheck disable=SC1091
[[ -f "$REPO_DIR/tools/deploy.env" ]] && source "$REPO_DIR/tools/deploy.env"
HA_CONFIG="${HA_CONFIG:-}"
HA_URL="${HA_URL:-http://homeassistant.local:8123}"
: "${HA_API_TOKEN_FILE:=$HOME/.ha_api_token}"
[[ -n "$HA_CONFIG" ]] || { echo "ERROR: set HA_CONFIG (cp tools/deploy.env.example tools/deploy.env and edit it)" >&2; exit 2; }
SRC_DIR="$REPO_DIR/custom_components/$COMPONENT"
DST_DIR="$HA_CONFIG/custom_components/$COMPONENT"
BACKUP_DIR="$REPO_DIR/backups"

RUN=0; BACKUP=1; RESTART=1; BUILD=1; EDITOR_ONLY=0

usage() { sed -n '2,13p' "$0"; cat <<EOF

Options:
  --run         actually deploy (default is a dry run)
  --editor      only sync custom_components/$COMPONENT/editor (no restart needed)
  --no-backup   skip the backup of the production copy
  --no-restart  skip the Home Assistant restart
  --no-build    do not rebuild the editor bundle first
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run) RUN=1 ;;
    --editor) EDITOR_ONLY=1; RESTART=0 ;;
    --no-backup) BACKUP=0 ;;
    --no-restart) RESTART=0 ;;
    --no-build) BUILD=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

[[ -d "$SRC_DIR" ]] || { echo "ERROR: source not found: $SRC_DIR" >&2; exit 1; }
[[ -d "$HA_CONFIG/custom_components" ]] || { echo "ERROR: $HA_CONFIG/custom_components not found (is the SMB share mounted?)" >&2; exit 1; }

TS=$(date +"%Y%m%d_%H%M%S")
echo "Deploy $COMPONENT"
echo "  from: $SRC_DIR"
echo "  to:   $DST_DIR"
echo "  mode: $([[ $EDITOR_ONLY -eq 1 ]] && echo 'editor only' || echo 'full')  build=$BUILD backup=$BACKUP restart=$RESTART"
echo "Planned:"
[[ $BUILD -eq 1 ]] && echo "  0. rebuild the editor bundle (tools/build_editor.sh)"
[[ $BACKUP -eq 1 && $EDITOR_ONLY -eq 0 ]] && echo "  1. backup $DST_DIR -> $BACKUP_DIR/${COMPONENT}_backup_$TS.tgz"
echo "  2. sync (rsync --delete --inplace)"
[[ $EDITOR_ONLY -eq 0 ]] && echo "  3. remove __pycache__ in production"
[[ $RESTART -eq 1 ]] && echo "  4. restart Home Assistant and wait for the integration to load"
if [[ $RUN -ne 1 ]]; then echo; echo "Dry run. Re-run with --run to apply."; exit 0; fi

if [[ $BUILD -eq 1 ]]; then
  if command -v npm >/dev/null 2>&1; then
    "$REPO_DIR/tools/build_editor.sh" || { echo "ERROR: editor build failed - refusing to deploy a half-built bundle" >&2; exit 1; }
  else
    echo "WARNING: npm not found - deploying the committed editor bundle as is"
  fi
fi
"$REPO_DIR/tools/build_editor.sh" --check || echo "WARNING: the editor bundle does not match the editor sources"

if [[ $BACKUP -eq 1 && $EDITOR_ONLY -eq 0 && -d "$DST_DIR" ]]; then
  mkdir -p "$BACKUP_DIR"
  tar -C "$(dirname "$DST_DIR")" -czf "$BACKUP_DIR/${COMPONENT}_backup_$TS.tgz" "$COMPONENT"
  echo "backup: $BACKUP_DIR/${COMPONENT}_backup_$TS.tgz"
fi

# --inplace: the HA Samba add-on vetoes "._*" names, and rsync's temporary files
# for __init__.py (".__init__.py.XXXXXX") would be rejected - silently skipping
# every __init__.py and leaving production half-updated.
RSYNC=(rsync -a --delete --inplace --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store')
mkdir -p "$DST_DIR"
if [[ $EDITOR_ONLY -eq 1 ]]; then
  "${RSYNC[@]}" "$SRC_DIR/editor/" "$DST_DIR/editor/"
else
  "${RSYNC[@]}" "$SRC_DIR/" "$DST_DIR/"
  find "$DST_DIR" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
fi
# Verify: a silent partial copy is the failure mode that bit us before
if ! diff -rq --exclude=__pycache__ "$SRC_DIR/$([[ $EDITOR_ONLY -eq 1 ]] && echo editor)" "$DST_DIR/$([[ $EDITOR_ONLY -eq 1 ]] && echo editor)" >/dev/null; then
  echo "ERROR: production differs from the repo after sync:" >&2
  diff -rq --exclude=__pycache__ "$SRC_DIR" "$DST_DIR" >&2 || true
  exit 1
fi
echo "synced and verified"

[[ $RESTART -eq 1 ]] || { echo "Restart skipped."; exit 0; }
[[ -r "$HA_API_TOKEN_FILE" ]] || { echo "ERROR: cannot read $HA_API_TOKEN_FILE; restart Home Assistant manually" >&2; exit 1; }
TOKEN="$(tr -d '\r\n' < "$HA_API_TOKEN_FILE")"
api() { curl -sS -m 15 -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"; }

echo "Restarting Home Assistant..."
# The call often returns 502/504 from the reverse proxy because HA goes down
# while answering it; that is expected. Wait for it to come back instead.
api -o /dev/null -w '  restart call: HTTP %{http_code}\n' -X POST "$HA_URL/api/services/homeassistant/restart" || true
sleep 15
for _ in $(seq 1 60); do
  code=$(api -o /dev/null -w '%{http_code}' "$HA_URL/api/" 2>/dev/null || true)
  [[ "$code" == "200" ]] && break
  sleep 5
done
[[ "$code" == "200" ]] || { echo "ERROR: Home Assistant did not come back within 5 min" >&2; exit 1; }
state=unknown
for _ in $(seq 1 12); do  # integrations keep loading for a while after the API is up
  state=$(api "$HA_URL/api/config/config_entries/entry?domain=$COMPONENT" 2>/dev/null | python3 -c '
import json, sys
try:
    entries = json.load(sys.stdin)
except ValueError:
    entries = []
print(",".join(e["state"] + (":" + e["reason"] if e.get("reason") else "") for e in entries) or "no entry")
' || echo unknown)
  [[ "$state" == loaded* || "$state" == *error* || "$state" == *failed* ]] && break
  sleep 5
done
echo "Home Assistant is back; $COMPONENT entry: $state"
[[ "$state" == loaded* ]] || exit 1
