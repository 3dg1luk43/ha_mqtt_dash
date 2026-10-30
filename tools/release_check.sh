#!/usr/bin/env bash
# iPad MQTT Dashboard - release preflight (what CI runs). Ported from
# ha_creality_ws / ha_washdata.
#
#   tools/release_check.sh                 verify only (safe; used by CI)
#   tools/release_check.sh --tag v0.6.0    also require the tag to match manifest.json
#                                          and the CHANGELOG entry to be dated
#
# Exit code is the number of failed checks. Every failure says what fixes it.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WANT_TAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) [[ $# -ge 2 ]] || { echo "--tag needs a value" >&2; exit 2; }; WANT_TAG="$2"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

FAILED=0
PY="./.venv/bin/python"; [[ -x "$PY" ]] || PY="python3"
COMPONENT="custom_components/ha_mqtt_dash"
pass() { printf '  \033[32mok\033[0m    %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; [[ -n "${2:-}" ]] && printf '        -> %s\n' "$2"; FAILED=$((FAILED + 1)); }
skip() { printf '  \033[33mskip\033[0m  %s\n' "$1"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

head_ "Version"
if OUT=$(WANT_TAG="$WANT_TAG" "$PY" - <<'PY'
import json, os, re, sys
mf = json.load(open("custom_components/ha_mqtt_dash/manifest.json"))["version"]
text = open("CHANGELOG.md", encoding="utf-8").read()
m = re.search(r"^##\s+\[?v?(\d[^\s\]]*)\]?\s*(?:[-–]\s*(.+?))?\s*$", text, re.M)
bad = []
if not m:
    bad.append("no '## <version> - <date|Unreleased>' heading in CHANGELOG.md")
else:
    cl, date = m.group(1), (m.group(2) or "").strip()
    if cl != mf:
        bad.append(f"manifest.json is {mf} but the top CHANGELOG entry is {cl}")
    want = (os.environ.get("WANT_TAG") or "").lstrip("v")
    if want and want != mf:
        bad.append(f"tag is {want} but manifest.json is {mf}")
    if want and not re.match(r"\d{4}-\d{2}-\d{2}$", date):
        bad.append(f"a tagged release needs a dated CHANGELOG entry, found '{date or 'nothing'}'")
print(mf)
for b in bad:
    print("PROBLEM: " + b, file=sys.stderr)
sys.exit(1 if bad else 0)
PY
); then pass "manifest.json and CHANGELOG.md agree ($OUT)"; else fail "version mismatch" "fix manifest.json / the top CHANGELOG.md heading"; fi

head_ "Integration"
if "$PY" -c "import ast,pathlib,sys; [ast.parse(p.read_text(encoding='utf-8'), str(p)) for d in ('$COMPONENT','tools') for p in pathlib.Path(d).rglob('*.py')]"; then pass "python parses"; else fail "python syntax error" "see the traceback above"; fi
RUFF="./.venv/bin/ruff"; [[ -x "$RUFF" ]] || RUFF="$(command -v ruff || true)"
if [[ -n "$RUFF" ]]; then
  if "$RUFF" check --isolated --select F,E9 -q "$COMPONENT" tools; then pass "ruff F,E9"; else fail "ruff found undefined names / unused imports" "ruff check --isolated --select F,E9 $COMPONENT tools"; fi
else skip "ruff not installed (pip install -r tools/requirements-test.txt)"; fi
if "$PY" - <<'PY'
import json, pathlib, sys
bad = []
for p in ["hacs.json", "custom_components/ha_mqtt_dash/manifest.json", "custom_components/ha_mqtt_dash/strings.json",
          *map(str, pathlib.Path("custom_components/ha_mqtt_dash/translations").glob("*.json"))]:
    try:
        json.load(open(p, encoding="utf-8"))
    except Exception as e:
        bad.append(f"{p}: {e}")
print("\n".join(bad), file=sys.stderr)
sys.exit(1 if bad else 0)
PY
then pass "JSON files parse"; else fail "invalid JSON" "see above"; fi
if cmp -s "$COMPONENT/strings.json" "$COMPONENT/translations/en.json"; then pass "strings.json == translations/en.json"; else fail "strings.json and translations/en.json differ" "edit strings.json, then cp it to translations/en.json"; fi

head_ "Editor bundle"
if tools/build_editor.sh --check >/dev/null 2>&1; then pass "committed bundle matches editor/ sources"; else fail "editor bundle is stale" "tools/build_editor.sh, then commit $COMPONENT/editor"; fi

head_ "Tests"
if "$PY" -c "import pytest" 2>/dev/null; then
  if "$PY" -m pytest -q tools/tests >/tmp/ha_mqtt_dash_pytest.log 2>&1; then pass "pytest tools/tests ($(tail -1 /tmp/ha_mqtt_dash_pytest.log))"; else tail -30 /tmp/ha_mqtt_dash_pytest.log; fail "tests failed" "$PY -m pytest tools/tests"; fi
else skip "pytest not installed (pip install -r tools/requirements-test.txt)"; fi

echo
if [[ $FAILED -eq 0 ]]; then echo "All release checks passed."; else echo "$FAILED check(s) failed."; fi
exit $FAILED
