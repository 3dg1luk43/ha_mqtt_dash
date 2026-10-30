# Dashboard editor

The drag-and-drop profile editor for iPad MQTT Dashboard. It ships inside the
integration and opens in Home Assistant at `/mqttdash-editor` (integration
options → **Open the dashboard editor**, or a panel's device page → **Visit**).
There it uses Home Assistant's own login over the integration's admin-only
WebSocket commands to list panels, load and deploy profiles.

## Development

```bash
cd editor
npm ci
npm run dev        # local preview (design + JSON export only; no HA connection)
npm run lint
../tools/build_editor.sh   # build for HA and copy into custom_components/ha_mqtt_dash/editor
```

The bundle in `custom_components/ha_mqtt_dash/editor/` is committed (HACS
users download it). Rebuild it with `tools/build_editor.sh` and commit it
together with the source change; CI fails when it is stale.
