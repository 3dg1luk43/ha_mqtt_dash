#!/usr/bin/env bash
# Install the MQTTDash app on a jailbroken iPad over SSH.
#
#   ./install_ipad.sh root@192.168.1.50            # detect iOS, pick the right build, install
#   ./install_ipad.sh root@ipad --kiosk            # also install the kiosk tweak (iOS 5.x)
#   ./install_ipad.sh root@ipad --deb my.deb       # install a specific package
#   ./install_ipad.sh root@ipad --dry-run          # only show what would happen
#
# Needs: OpenSSH on the iPad (Cydia "OpenSSH"), and ssh on this machine. The
# packages come from ./releases next to this script, or are downloaded from
# GitHub when the script is used on its own.
set -euo pipefail

REPO="3dg1luk43/ha_mqtt_dash"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET=""; KIOSK=0; DEB=""; DRY=0; YES=0; RESPRING=1; VARIANT=""

usage() { sed -n '2,12p' "$0"; cat <<'EOF'

Options:
  --kiosk           also install the MQTTDash kiosk tweak (auto-launch, lock-screen bypass; iOS 5.x)
  --variant V       force legacy (armv7, iOS 5-10) or modern (arm64, iOS 11+)
  --deb FILE|URL    install this package instead of the newest one from releases/
  --no-respring     don't restart SpringBoard afterwards
  -y, --yes         don't ask for confirmation
  --dry-run         detect and print the plan, change nothing
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kiosk) KIOSK=1 ;;
    --variant) VARIANT="${2:-}"; shift ;;
    --deb) DEB="${2:-}"; shift ;;
    --no-respring) RESPRING=0 ;;
    -y|--yes) YES=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    *) TARGET="$1" ;;
  esac
  shift
done
[[ -n "$TARGET" ]] || { usage; exit 2; }
[[ "$TARGET" == *@* ]] || TARGET="root@$TARGET"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# ── SSH: old iPads only speak legacy algorithms; add them only when needed ──
SSH_OPTS=(-o ConnectTimeout=10 -o ServerAliveInterval=15)
legacy_opts() {
  local opt out=()
  for opt in "HostKeyAlgorithms=+ssh-rsa" "PubkeyAcceptedAlgorithms=+ssh-rsa" \
             "KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1" \
             "Ciphers=+aes128-cbc,aes256-ctr"; do
    # Keep only what this ssh client understands (new clients dropped some)
    ssh -G -o "$opt" localhost >/dev/null 2>&1 && out+=(-o "$opt")
  done
  printf '%s\n' "${out[@]}"
}
run() { ssh "${SSH_OPTS[@]}" "$TARGET" "$@"; }

say "Connecting to $TARGET"
if ! run true 2>/dev/null; then
  while IFS= read -r o; do [[ -n "$o" ]] && SSH_OPTS+=("$o"); done < <(legacy_opts)  # bash 3.2 (macOS) safe
  run true || die "cannot SSH into $TARGET (is OpenSSH installed on the iPad? default root password is 'alpine' - change it)"
fi

INFO="$(run 'v=$(sw_vers -productVersion 2>/dev/null || sysctl -n kern.osproductversion 2>/dev/null); m=$(sysctl -n hw.machine 2>/dev/null || uname -m); r=no; [ -d /var/jb ] && r=yes; d=no; command -v dpkg >/dev/null && d=yes; echo "$v|$m|$r|$d"')"
IFS='|' read -r IOS MODEL ROOTLESS HAS_DPKG <<<"$INFO"
[[ -n "$IOS" ]] || die "could not read the iOS version"
[[ "$HAS_DPKG" == yes ]] || die "dpkg not found on the iPad (is it jailbroken with Cydia?)"
MAJOR="${IOS%%.*}"
say "Found $MODEL on iOS $IOS"
if [[ "$ROOTLESS" == yes ]]; then
  die "this is a rootless jailbreak (/var/jb); the packages are built for rootful jailbreaks"
fi
if [[ -z "$VARIANT" ]]; then
  if (( MAJOR <= 10 )); then VARIANT=legacy; else VARIANT=modern; fi
fi
[[ "$VARIANT" == legacy || "$VARIANT" == modern ]] || die "--variant must be legacy or modern"

# ── pick the package ─────────────────────────────────────────────────────────
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fetch() {  # fetch <url> <out>
  curl -fsSL --retry 2 -o "$2" "$1" || die "download failed: $1"
}
newest_remote() {  # newest_remote <glob-regex>
  curl -fsSL "https://api.github.com/repos/$REPO/contents/releases" \
    | grep -o '"name": *"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' | grep -E "$1" | sort -V | tail -1
}
pick() {  # pick <regex> -> path to a local .deb
  local regex="$1" name
  if [[ -d "$HERE/releases" ]]; then
    name="$(ls "$HERE/releases" 2>/dev/null | grep -E "$regex" | sort -V | tail -1 || true)"
    [[ -n "$name" ]] && { echo "$HERE/releases/$name"; return; }
  fi
  name="$(newest_remote "$regex" || true)"
  [[ -n "$name" ]] || die "no package matching $regex found locally or on GitHub"
  fetch "https://raw.githubusercontent.com/$REPO/main/releases/$name" "$TMP/$name"
  echo "$TMP/$name"
}
if [[ -n "$DEB" ]]; then
  if [[ "$DEB" =~ ^https?:// ]]; then fetch "$DEB" "$TMP/app.deb"; APP_DEB="$TMP/app.deb"; else APP_DEB="$DEB"; fi
else
  APP_DEB="$(pick "^com\.3dg1luk43\.mqttdash_.*\+${VARIANT}_iphoneos-arm\.deb$")"
fi
[[ -f "$APP_DEB" ]] || die "package not found: $APP_DEB"
KIOSK_DEB=""
if [[ $KIOSK -eq 1 ]]; then
  (( MAJOR == 5 )) || say "note: the kiosk tweak is built and tested for iOS 5.x only"
  KIOSK_DEB="$(pick '^com\.3dg1luk43\.mqttdash-kiosk_.*_iphoneos-arm\.deb$')"
fi

say "Plan:"
echo "    app:    $(basename "$APP_DEB")  ($VARIANT)"
[[ -n "$KIOSK_DEB" ]] && echo "    kiosk:  $(basename "$KIOSK_DEB")"
echo "    then:   refresh icons$([[ $RESPRING -eq 1 ]] && echo ', restart SpringBoard')"
[[ $DRY -eq 1 ]] && { say "Dry run - nothing changed."; exit 0; }
if [[ $YES -ne 1 ]]; then
  read -r -p "Install onto $TARGET? [Y/n] " ans
  [[ -z "$ans" || "$ans" =~ ^[Yy] ]] || exit 1
fi

# ── install ──────────────────────────────────────────────────────────────────
# Plain ssh + cat: works even where scp/sftp are missing (iOS 5 OpenSSH builds)
say "Copying package"
run 'cat > /var/root/mqttdash.deb' < "$APP_DEB"
[[ -n "$KIOSK_DEB" ]] && run 'cat > /var/root/mqttdash-kiosk.deb' < "$KIOSK_DEB"

say "Installing"
run 'set -e
for p in com.yourorg.mqttdash com.yourorg.mqttdash-legacy com.yourorg.mqttdash-modern \
         com.3dg1luk43.mqttdash com.3dg1luk43.mqttdash-legacy com.3dg1luk43.mqttdash-modern; do
  new=$(dpkg-deb -f /var/root/mqttdash.deb Package)
  [ "$p" = "$new" ] && continue
  dpkg -s "$p" >/dev/null 2>&1 && dpkg -r "$p" >/dev/null 2>&1 && echo "    removed old package $p" || true
done
dpkg -i /var/root/mqttdash.deb
if [ -f /var/root/mqttdash-kiosk.deb ]; then dpkg -i /var/root/mqttdash-kiosk.deb; fi
rm -f /var/root/mqttdash.deb /var/root/mqttdash-kiosk.deb
if command -v uicache >/dev/null 2>&1; then
  uicache -p /Applications/mqttdash.app 2>/dev/null || uicache 2>/dev/null || su mobile -c uicache 2>/dev/null || true
fi'
if [[ $RESPRING -eq 1 ]]; then
  say "Restarting SpringBoard"
  run 'killall SpringBoard 2>/dev/null || killall -9 SpringBoard 2>/dev/null || true'
fi

say "Done. On the iPad: open MQTTDash and enter your MQTT broker and a device ID."
echo "    Then in Home Assistant: install 'iPad MQTT Dashboard' from HACS and design the layout in"
echo "    Settings > Devices & services > iPad MQTT Dashboard > Configure > Open the dashboard editor."
