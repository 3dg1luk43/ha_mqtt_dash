# MQTT namespace and topics

The entire integration uses a fixed `mqttdash/*` namespace — no custom bases or configurable prefixes.

## Topic map

| Topic | Direction | Retained | Description |
|-------|-----------|----------|-------------|
| `mqttdash/config/<device_id>/config` | HA → iPad | Yes | Profile JSON |
| `mqttdash/dev/<device_id>/hello` | iPad → HA | No | Device hello / identify |
| `mqttdash/dev/<device_id>/status` | iPad (LWT) | Yes | `online` / `offline` presence |
| `mqttdash/dev/<device_id>/telemetry` | iPad → HA | No | Battery level and device info |
| `mqttdash/dev/<device_id>/settings` | HA → iPad | Yes | Device settings (brightness, orientation, keep-awake, screensaver) |
| `mqttdash/dev/<device_id>/notify` | HA → iPad | No | Push notification payload |
| `mqttdash/dev/<device_id>/request` | iPad → HA | No | App requests (snapshot, onboard) |
| `mqttdash/cmd/<entity_id>` | iPad → HA | No | Widget action commands |
| `mqttdash/statestream/<domain>/<object>/state` | HA → iPad | Yes | Entity state mirror |
| `mqttdash/statestream/<domain>/<object>/attributes/<key>` | HA → iPad | Yes | Entity attribute mirror |

The integration auto-wires widget topics based on entity IDs. Profiles never contain MQTT topic strings.

---

## Payload reference

### Config (HA → iPad)

Published retained to `mqttdash/config/<device_id>/config`. Full JSON profile — see [Profiles and widgets](profiles_and_widgets.md) for the schema.

Top-level fields published by the integration:

- `version` — config schema version (currently `1`)
- `device_id` — target device ID
- `device` — device settings object (echoed back from store)
- `ui` — grid, pages/widgets, navbar configuration
- `topics` — device topic strings injected for the app

### Device hello (iPad → HA)

Published non-retained to `mqttdash/dev/<device_id>/hello`:

```json
{
  "guid": "stable-uuid-per-install",
  "prev_id": "old-device-id",
  "screen": { "width": 1024, "height": 768, "scale": 1.0, "orientation": "landscape" }
}
```

`guid` is a stable identifier generated at first launch and preserved across renames. `prev_id` triggers device migration when a `device_id` changes.

### Device telemetry (iPad → HA)

Published non-retained to `mqttdash/dev/<device_id>/telemetry`:

```json
{ "battery": 87, "charging": false }
```

The integration uses this to update the `sensor.<device_id>_battery` entity.

### Device settings (HA → iPad)

Published retained to `mqttdash/dev/<device_id>/settings`. All fields are optional — app applies whichever are present:

```json
{
  "brightness": 0.8,
  "keep_awake": true,
  "orientation": "landscape",
  "screensaverTimeout": 120,
  "screensaverFontSize": 48
}
```

| Field | Type | Description |
|-------|------|-------------|
| `brightness` | number 0..1 | Screen brightness |
| `keep_awake` | boolean | Prevent screen sleep |
| `orientation` | string | `"auto"` \| `"portrait"` \| `"landscape"` |
| `screensaverTimeout` | number | Idle seconds before screensaver (0 = disabled) |
| `screensaverFontSize` | number | Screensaver clock font size in pt (0 = device default) |

### Notification (HA → iPad)

Published non-retained to `mqttdash/dev/<device_id>/notify`:

```json
{ "title": "Laundry", "message": "Washing machine done" }
```

`title` is optional. The app shows a banner overlay and dismisses the screensaver if active.

### Commands (iPad → HA)

Published non-retained to `mqttdash/cmd/<entity_id>`:

```json
{ "action": "turn_on" }
{ "action": "turn_off" }
{ "action": "toggle" }
{ "action": "press" }
{ "action": "turn_on", "brightness": 128 }
{ "action": "set_hvac_mode", "hvac_mode": "heat" }
{ "action": "set_temperature", "temperature": 21.5 }
{ "action": "media_play_pause" }
{ "action": "media_next_track" }
{ "action": "media_previous_track" }
{ "action": "media_seek", "position": 42.0 }
```

### App requests (iPad → HA)

Published non-retained to `mqttdash/dev/<device_id>/request`:

```json
{ "action": "snapshot" }
{ "action": "onboard", "guid": "stable-uuid" }
```

`snapshot` requests a full state republish. `onboard` re-admits a previously purged device.

---

## HTTP API endpoints

Both endpoints require:
- **Local network only** — RFC-1918 / loopback addresses. Requests from public IPs are rejected with HTTP 403 even with a valid token.
- **Bearer token** — `Authorization: Bearer <long_lived_token>` (the same auth the HA frontend uses)
- **API Access enabled** — Integration Options → API Access (time-limited unlock; auto-closes after 10 minutes of inactivity)

### `POST /api/ha_mqtt_dash/apply_profile`

Saves a profile for a device and triggers an immediate MQTT republish.

Request:
```json
{ "device_id": "my_ipad", "profile": { "ui": { ... } } }
```

Response:
```json
{ "status": "ok", "device_id": "my_ipad" }
```

Rate limited: 20 requests per 60 seconds per IP. Body size limit: 512 KB.

### `GET /api/ha_mqtt_dash/entities`

Returns a sorted list of all entity IDs known to HA. Used by the profile editor for entity autocomplete.

Response:
```json
{ "entities": ["binary_sensor.door", "climate.living_room", "light.bedroom"] }
```

---

## Services

| Service | Description |
|---------|-------------|
| `ha_mqtt_dash.push_config` | Republish retained configs for all devices |
| `ha_mqtt_dash.reload_config` | Transient reload then republish configs |
| `ha_mqtt_dash.set_device_settings` | Send settings to a device (retained) |
| `ha_mqtt_dash.publish_snapshot` | Full state snapshot for all mirrored entities |
| `ha_mqtt_dash.set_device_profile` | Overwrite a device's profile in HA Store and republish |
| `ha_mqtt_dash.republish_reload_all` | Debounced reload + republish cycle |
| `ha_mqtt_dash.prune_unassigned` | Remove unassigned devices and purge retained topics |
| `ha_mqtt_dash.dump_store` | Debug: log HA Store contents |
| `ha_mqtt_dash.dump_runtime_cfg` | Debug: log merged runtime config |
| `ha_mqtt_dash.dump_device_config` | Debug: log a single device's resolved config |

---

## Notify services

In addition to the integration services, each registered device gets a dynamic HA notify service:

```
notify.mqttdash_<device_id>
```

Hyphens in `device_id` become underscores. Fields: `message` (required), `title` (optional).

```yaml
service: notify.mqttdash_kitchen_ipad
data:
  title: "Alert"
  message: "Oven left on"
```

---

## Retention policy

- **Retained:** device configs, device status, device settings, mirrored entity states and attributes
- **Non-retained:** device hello, telemetry, notifications, app requests, command messages
- Removed attributes are purged by publishing an empty retained payload to the attribute topic

---

## Onboard / offboard

**Onboard (device → HA):** Publish `{ "action": "onboard", "guid": "..." }` to `mqttdash/dev/<id>/request` to re-admit a previously purged device.

**Offboard (HA → device):** When a device is deleted in HA, the integration clears all retained topics and publishes `{ "action": "offboard" }` to the device request topic. The app stops MQTT, clears its stored Device ID, and returns to the welcome screen. The stable GUID is preserved so the device can re-onboard if needed.
