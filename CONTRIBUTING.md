# Contributing

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-test.txt
cd editor && npm ci && cd ..
```

## Before you push

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check --isolated --select F,E9 custom_components tools
(cd editor && npm run lint)
tools/build_editor.sh          # if you touched editor/ - commit the rebuilt bundle too
tools/release_check.sh
```

CI runs the same checks plus hassfest and HACS validation.

## Where things live

- **Integration:** `custom_components/ha_mqtt_dash/`.
- **Dashboard editor:** `editor/`. Home Assistant serves the built copy in
  `custom_components/ha_mqtt_dash/editor/` as the panel at `/mqttdash-editor`.
- **iPad packages:** `releases/`, built from the private iOS app repo. Users
  install them with `./install_ipad.sh`.

## Testing against a real Home Assistant

Copy `tools/deploy.env.example` to `tools/deploy.env`, point it at a mounted HA
config directory and a token file, then:

```bash
tools/deploy_to_ha.sh          # dry run
tools/deploy_to_ha.sh --run    # backup, build, sync, restart, wait for the entry to load
```

## Releases

1. Bump the version in `manifest.json` in its own commit.
2. Date the CHANGELOG heading: `## X.Y.Z - YYYY-MM-DD`.
3. Push the `vX.Y.Z` tag. CI runs the preflight and drafts a GitHub release
   with the notes and the newest iPad packages attached. Publish it by hand.
