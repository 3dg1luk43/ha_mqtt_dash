# CLAUDE.md

Guidance for Claude Code in this repository: rules and traps. The repo-process
model is `/root/ha_washdata` and `/root/ha_creality_ws`; adapt, don't copy.

## Project

Public repo for **iPad MQTT Dashboard**: the Home Assistant integration
(`custom_components/ha_mqtt_dash`), the dashboard editor it hosts as an HA
panel (`editor/`, React + Vite), and the prebuilt iPad packages (`releases/`).
The iOS app source lives in the **private** repo `/root/mqttdash`
(Objective-C, Theos); only its built `.deb` files land here.

## Layout

| Path | What |
|------|------|
| `custom_components/ha_mqtt_dash/` | Integration (what HACS installs). `editor/` inside it is the **built** editor bundle (committed). `frontend/` is the panel host element. |
| `editor/` | Editor source. Embedded mode (`src/utils/haEmbed.js`) talks to the integration's WebSocket commands. |
| `releases/` | iPad `.deb` packages (legacy armv7, modern arm64, kiosk tweak), built in `/root/mqttdash`. |
| `install_ipad.sh` | User-facing installer: app (+ kiosk) onto a jailbroken iPad over SSH. |
| `tools/` | `deploy_to_ha.sh` (dev deploy), `build_editor.sh`, `release_check.sh`, `tests/`. |
| `docs/` | User docs (linked from README). |

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements-test.txt
.venv/bin/python -m pytest                    # stubbed-HA unit tests (tools/tests), < 1 s
.venv/bin/ruff check --isolated --select F,E9 custom_components tools
tools/build_editor.sh                          # build editor/ -> custom_components/ha_mqtt_dash/editor (commit it)
tools/build_editor.sh --check                  # is the committed bundle current?
tools/release_check.sh [--tag v0.6.0]          # release preflight (what CI runs)
tools/deploy_to_ha.sh                          # dry run; --run deploys to the dev HA (settings: tools/deploy.env)
tools/deploy_to_ha.sh --run --editor           # editor bundle only, no HA restart
./install_ipad.sh root@<ipad> [--kiosk]        # install the app from releases/
cd editor && npm ci && npm run dev             # editor UI preview outside HA (no HA connection)
```

## What the tests can and cannot prove

`tools/tests` stubs Home Assistant (`conftest.py`): every `homeassistant.*` name
is a MagicMock, so config building, attribute encoding, battery care, command
routing, translation coverage and bundle freshness are covered, but **nothing
HA validates** (service schemas, config/options flows, entity wiring, the
panel/WebSocket registration). For those, deploy to the dev HA
(`tools/deploy_to_ha.sh --run`) and check: the entry is `loaded`, the WebSocket
commands answer (`ha_mqtt_dash/devices`), and the panel opens at
`/mqttdash-editor`. Say in the report what was verified where.

## Rules

- **Never edit production directly.** `/root/ha_config` (the SMB mount of the
  live HA config) is written only by `tools/deploy_to_ha.sh`. Do not edit files
  there, do not deploy or restart HA unless the user asked for it.
- **The editor bundle is generated.** After editing `editor/`, run
  `tools/build_editor.sh` and commit the bundle in the same commit (CI and
  `test_packaging.py` fail on a stale bundle).
- **Every user-visible flow string** lives in `strings.json`, copied verbatim to
  `translations/en.json` (`test_translations.py`). New options-flow steps,
  menu items and abort reasons need entries.
- **Profile JSON is the contract** between editor, integration and iPad app.
  New widget fields: editor config panel + export, `mqtt_bridge._normalize_one`
  (fields are allowlisted there), the app's `ConfigModel`, and
  `docs/profiles_and_widgets.md`.
- **The iPad side is iOS 5.1 / iPad 1.** Anything published to devices (topics,
  payloads, image sizes) must be cheap to parse; images go out as small
  baseline JPEGs.
- **Device commands are allowlisted**: only entities that are controllable
  widgets in a published profile (`MqttBridge._commandable`). Keep it that way.
- No secrets in tracked files (tokens, hostnames of the dev setup): those go in
  `tools/deploy.env` (gitignored).
- Commits: conventional, lowercase (`fix: ...`, `feat(editor): ...`). Version
  bumps in their own commit. CHANGELOG heading `## X.Y.Z - Unreleased` until
  release, then `## X.Y.Z - YYYY-MM-DD`; `manifest.json` version must match.

## Traps

- **HA Samba share vetoes `._*` names.** rsync temp files for `__init__.py` are
  `.__init__.py.XXXX`, so a plain rsync silently skips every `__init__.py`.
  `deploy_to_ha.sh` uses `--inplace` and verifies the copy; keep both.
- **The restart call returns 502** through the reverse proxy while HA goes down;
  `deploy_to_ha.sh` waits for the API and the config entry instead of trusting it.
- **Static files vs Python.** Editor/panel JS changes are live after a sync
  (no restart); any `.py`, `manifest.json` or translation change needs a restart.
- **Single-key profiles.** `{"ui": {...}}` is a real profile, not a
  `{"main_panel": {...}}` wrapper; `_PROFILE_KEYS` guards the unwrap heuristic.
- **The panel is a custom panel** (`frontend/mqttdash-editor-panel.js`), not
  HA's `iframe` panel, so HA draws no toolbar. It has no `sidebar_title` on
  purpose (not in the sidebar); on narrow layouts it shows its own menu button.
- The iPad test device is reachable only while its screen is on; see the memory
  note / `/root/mqttdash/CLAUDE.md` for waking it and taking screenshots.
