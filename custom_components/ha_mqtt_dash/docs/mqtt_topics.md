# MQTT namespace and topics

Fixed namespace (no custom bases):

- Configs (retained): `mqttdash/config/<device_id>/config`
- Device topics:
    - Settings (retained): `mqttdash/dev/<device_id>/settings`
    - Hello (non‑retained): `mqttdash/dev/<device_id>/hello`
    - Status/LWT (retained): `mqttdash/dev/<device_id>/status` (online/offline)
    - Notify (non‑retained): `mqttdash/dev/<device_id>/notify`
    - Request (non‑retained): `mqttdash/dev/<device_id>/request` (e.g., `{ "action": "snapshot" | "onboard" }`)
- Commands (non‑retained): `mqttdash/cmd/<entity_id>`
- Mirrored state (retained, built‑in by the integration):
    - State: `mqttdash/statestream/<domain>/<object>/state`
    - Attributes: `mqttdash/statestream/<domain>/<object>/attributes[/<key>]`

The integration auto‑wires widget topics under this namespace. Profiles never include MQTT topics.

## Parameter reference

### Top-level (published to `mqttdash/config/<device_id>/config`):
- `version`: number — config schema version (currently 1)
- `device_id`: string — target device ID
- `device`: object — may include `screen` info (from device hello). Not used for settings.
- `ui`: object — grid and widgets (see below)
- `topics`: object — device topics
    - `settings`: string — `mqttdash/dev/<device_id>/settings` (retained)
    - `hello`: string — `mqttdash/dev/<device_id>/hello`
    - `status`: string — `mqttdash/dev/<device_id>/status` (retained LWT online/offline)

### Device hello payload (app → HA on `mqttdash/dev/<id>/hello`):
- JSON with optional fields:
    - `guid`: string — stable unique identifier for device instance
    - `prev_id`: string — previous device_id to support seamless rename/migration
    - `screen`: object — as provided by the client, persisted and echoed back under `device.screen` in config

### Device status (presence):
- `mqttdash/dev/<id>/status`: retained `online`/`offline` via MQTT LWT

### Commands (app → HA via integration):
- Published by the app to `mqttdash/cmd/<entity_id>` with JSON payloads:
    - `{ "action": "turn_on" }`
    - `{ "action": "turn_off" }`
    - `{ "action": "toggle" }`
    - `{ "action": "press" }` (for `button.*`)
    - Lights can include `{ "brightness": 0..255 }`

### Device settings (HA → app):
- `mqttdash/dev/<id>/settings` (retained) JSON fields (all optional; app applies if present):
    - `brightness`: number 0..1 (clamped)
    - `keep_awake`: boolean
    - `orientation`: `auto` | `portrait` | `landscape`

### Mirroring configuration (in integration options):
- `mirror_entities`: array of `domain.object` strings
- Behavior:
    - Retained state at `mqttdash/statestream/<domain>/<object>/state`
    - Retained attributes at `mqttdash/statestream/<domain>/<object>/attributes/<key>`
    - Snapshot publishes full states/attributes: auto at HA startup and on demand via service
    - Dedupe avoids redundant publishes; removed attributes are purged by sending empty retained values

## Admin/services (HA → integration):
 - `ha_mqtt_dash.push_config` — republish retained configs for all devices
 - `ha_mqtt_dash.reload_config` — transient reload then republish configs
 - `ha_mqtt_dash.set_device_settings` — send settings to a device (retained)
 - `ha_mqtt_dash.publish_snapshot` — publish snapshot for mirrored entities (retained)
 - `ha_mqtt_dash.set_device_profile` — overwrite a device’s profile JSON in HA Store and republish
 - `ha_mqtt_dash.dump_store` — log/publish Store JSON
 - `ha_mqtt_dash.dump_runtime_cfg` — log/publish merged runtime cfg
 - `ha_mqtt_dash.republish_reload_all` — trigger reload+republish cycle
 - `ha_mqtt_dash.prune_unassigned` — remove unassigned devices and purge retained topics
 - `ha_mqtt_dash.dump_device_config` — build/log a single device’s config; optionally publish to a debug topic

## Notifications (HA → iPad popup)
- Domain service: `ha_mqtt_dash.notify` with fields: `device_id` (or `ha_device` via device selector), `message` (required), `title` (optional).
- Per-device services: dynamic `notify.mqttdash_<device_id>` (hyphens become underscores). Fields: `message` (required), `title` (optional).
Behavior: Publishes a non‑retained JSON payload to `mqttdash/dev/<device_id>/notify`. The iPad shows a popup banner with sound/vibrate.

## Retention policy
- Retained: device configs, device status/hello reflection, device settings, mirrored entity states and attributes.
- Non‑retained: device requests (e.g., reload, snapshot) and entity command messages.

## Onboard/offboard
- Onboard (device → HA): publish `{ "action": "onboard", "guid": "..." }` to `mqttdash/dev/<id>/request` to re‑admit a previously purged device.
- Offboard (HA → device): when a device is purged, the integration clears retained topics and publishes `{ "action": "offboard" }` transiently to `.../request` and retained to `.../settings`. The app clears its stored Device ID and returns to the welcome screen.
