# MQTT namespace and topics

The entire integration uses a fixed `mqttdash/*` namespace — no custom bases or configurable prefixes.

## Topic map

| Topic | Direction | Retained | Description |
|-------|-----------|----------|-------------|
| `mqttdash/config/<device_id>/config` | HA → iPad | Yes | Profile JSON |
| `mqttdash/dev/<device_id>/hello` | iPad → HA | No | Device hello / identify |
| `mqttdash/dev/<device_id>/status` | iPad (LWT) | Yes | `online` (awake) / `sleeping` (screen off, background link) / `offline` |
| `mqttdash/dev/<device_id>/telemetry` | iPad → HA | No | Battery level and device info |
| `mqttdash/dev/<device_id>/settings` | HA → iPad | Yes | Device settings (brightness, orientation, keep-awake, screensaver) |
| `mqttdash/dev/<device_id>/notify` | HA → iPad | No | Push notification payload |
| `mqttdash/dev/<device_id>/heartbeat` | HA → iPad | Yes | Periodic freshness beat (`{"ts":<unix>,"seq":<n>}`, ~30 s) |
| `mqttdash/dev/<device_id>/request` | both | No | App requests (snapshot, onboard); HA requests (`wake`, `report`, `sleep`, video) |
| `mqttdash/dev/<device_id>/ack` | iPad → HA | No | `{"rid"}`: the panel got a request or notification that carries an id (see [Delivery](#delivery)) |
| `mqttdash/dev/<device_id>/camera` | iPad → HA | No | Camera viewer heartbeat `{"entity_id","active","width","interval"}` (~15 s while shown) |
| `mqttdash/dev/<device_id>/debug` | → iPad | No | Diagnostics (screenshot, optionally delayed / tap / page / `test_command` through the command outbox); only honored with "Verbose MQTT log" on |
| `mqttdash/cmd/<entity_id>` | iPad → HA | No | Widget action commands (only for entities that are controllable widgets in a profile) |
| `mqttdash/statestream/<domain>/<object>/state` | HA → iPad | Yes | Entity state mirror |
| `mqttdash/statestream/<domain>/<object>/attributes/<key>` | HA → iPad | Yes | Entity attribute mirror (lists/dicts as JSON, datetimes ISO 8601, `None` as empty) |
| `mqttdash/art/<entity_id>` | HA → iPad | Yes | Album art / print thumbnail JPEG (≤ 320 px); empty = none |
| `mqttdash/camera/<entity_id>/frame` | HA → iPad | No | Camera frame JPEG, sent only while a device views the camera |

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

Published retained to `mqttdash/dev/<device_id>/settings` whenever one of the panel's setting entities changes, always with all of them (so a reconnecting panel gets the full set). The app applies whichever fields are present:

```json
{
  "brightness": 0.8,
  "keep_awake": true,
  "orientation": "landscape",
  "screensaver_timeout": 120
}
```

| Field | Type | Description |
|-------|------|-------------|
| `brightness` | number 0.05..1 | Screen brightness (the HA entity shows 5–100 %) |
| `keep_awake` | boolean | Prevent screen sleep |
| `orientation` | string | `"auto"` \| `"portrait"` \| `"landscape"` |
| `screensaver_timeout` | number | Seconds without a touch before the clock screensaver; 0 = off |

### Notification (HA → iPad)

Published non-retained to `mqttdash/dev/<device_id>/notify`:

```json
{ "title": "Laundry", "message": "Washing machine done" }
```

`title` is optional. The app shows a banner overlay and dismisses the screensaver if active. A sleeping panel gets it over its background link, turns its screen on and shows it. HA adds a `rid` and re-sends until the panel acknowledges it (see [Delivery](#delivery)).

### Freshness heartbeat (HA → iPad)

Published **retained** to `mqttdash/dev/<device_id>/heartbeat` roughly every 30 s:

```json
{ "ts": 1717977600, "seq": 42 }
```

`ts` is a UTC unix timestamp and `seq` increments each beat. The app tracks the
time since the last heartbeat (and any other inbound traffic) and, if it has seen at
least one heartbeat, forces an MQTT reconnect when data goes stale (~90 s). This
recovers from a backend that is connected but no longer publishing. Older integration
versions that never publish a heartbeat simply leave the watchdog dormant.

### Commands (iPad → HA)

Published non-retained with QoS 1 to `mqttdash/cmd/<entity_id>`; each carries a `cid` (see [Delivery](#delivery)):

```json
{ "action": "turn_on", "cid": "kitchen-6ae7235b-1" }
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
{ "action": "open_cover" }
{ "action": "close_cover" }
{ "action": "stop_cover" }
{ "action": "set_cover_position", "position": 60 }
{ "action": "open_cover_tilt" }
{ "action": "close_cover_tilt" }
{ "action": "set_cover_tilt_position", "position": 30 }
```

### App requests (iPad → HA)

Published non-retained to `mqttdash/dev/<device_id>/request`:

```json
{ "action": "snapshot" }
{ "action": "onboard", "guid": "stable-uuid" }
```

`snapshot` requests a full state republish. `onboard` re-admits a previously purged device.

### Panel requests (HA → iPad)

Same topic, from HA:

```json
{ "action": "wake" }
{ "action": "report" }
{ "action": "sleep" }
{ "action": "play_video", "url": "http://…/master.m3u8", "title": "…", "start": 30, "rid": "6ece03d5" }
{ "action": "video_control", "cmd": "pause", "rid": "…" }
{ "action": "stop_video", "rid": "…" }
```

`wake` turns the screen on (via the kiosk tweak). `report` publishes battery / charging telemetry without waking the screen. `sleep` locks it again after a battery check. All reach a sleeping panel through its background link; a video request turns the screen on and starts once the app is in front.

## Delivery

MQTT only reaches a panel whose link is up, and a link can die without either side noticing (Wi-Fi asleep, the broker keeps a sleeping panel's session for 15 min). So both directions confirm what matters:

- **Taps (iPad → HA):** a command is published with QoS 1 and kept until the broker's PUBACK. A tap while the link is down reconnects at once; no PUBACK within 5 s means the link is dead: the app reconnects and sends it again. While commands wait, reconnects are retried every 2 s, and the panel shows "Reconnecting… N actions waiting". A command older than 2 min is dropped (with a notice). HA runs each `cid` once, so a command sent twice switches nothing twice.
- **Video and notifications (HA → iPad):** HA adds a `rid` and keeps the request until the panel publishes `{"rid": …}` to `mqttdash/dev/<device_id>/ack`. Unanswered, it is re-sent (after 4, 10 and 20 s, then every 15 s), the panel is asked to `wake` after 4 s and, if it has a charger plug in Battery care, woken by power after 12 s (at most every 3 min). Anything waiting goes out again the moment the panel shows up (hello, status, telemetry). Time to live: `play_video` 3 min, `stop_video` 1 min, `video_control` 30 s, notifications 15 min. A stop or a pause never wakes a panel. The panel acknowledges every copy and acts on the first.
- `wake`, `report` and `sleep` have no `rid`: Battery care has its own timeouts and fallbacks.

---

## Editor WebSocket commands

The dashboard editor panel (`/mqttdash-editor`) talks to Home Assistant over its normal WebSocket connection. All commands require an **admin** user:

| Command | Payload | Result |
|---------|---------|--------|
| `ha_mqtt_dash/devices` | – | `{"devices": [{"device_id", "has_profile", "battery", "orientation"}]}` |
| `ha_mqtt_dash/get_profile` | `device_id` | `{"device_id", "profile"}` |
| `ha_mqtt_dash/apply_profile` | `device_id`, `profile` | saves the profile and republishes it to the panel |

Profiles are limited to 20 pages, 200 widgets per page, 500 widgets in total and 4096 characters per string.

---

## Actions

| Action | Description |
|--------|-------------|
| `ha_mqtt_dash.reload` | Publish every panel's config again and make the panels reload it |
| `ha_mqtt_dash.set_device_profile` | Replace a panel's profile in the HA Store and republish it |
| `notify.send_message` on `notify.<panel>` | Publish `{"message", "title"?}` to `mqttdash/dev/<device_id>/notify` |

Each panel also has a notify entity (`notify.send_message`), which publishes the same payload.

---

## Retention policy

- **Retained:** device configs, device status, device settings, mirrored entity states and attributes
- **Non-retained:** device hello, telemetry, notifications, app requests, command messages
- Removed attributes are purged by publishing an empty retained payload to the attribute topic

---

## Onboard / offboard

**Onboard (device → HA):** Publish `{ "action": "onboard", "guid": "..." }` to `mqttdash/dev/<id>/request` to re-admit a previously purged device.

**Offboard (HA → device):** When a device is deleted in HA, the integration clears all retained topics and publishes `{ "action": "offboard" }` to the device request topic. The app stops MQTT, clears its stored Device ID, and returns to the welcome screen. The stable GUID is preserved so the device can re-onboard if needed.
