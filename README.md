# Home Assistant MQTT Dashboard (iPad iOS 5.1.1)

This is the definitive guide for setting up and using the iPad MQTT Dashboard with the `ha_mqtt_dash` Home Assistant integration.

- App: Objective‑C (UIKit, iOS 5 APIs) targeting iPad 1. Theos toolchain for build.
- Transport: MQTT 3.1.1 over TCP (no TLS/WebSockets).
- Design: Event‑driven with retained device config and retained entity statestream; stateless JSON commands per widget.
- MQTT namespace is fixed to mqttdash/* (no user overrides): configs, device topics, commands, and statestream.

## Table of contents
- [Supported devices](#supported-devices)
- [Installation](#installation)
- [Home Assistant integration overview](#home-assistant-integration-overview)
- [Device provisioning and config flow](#device-provisioning-and-config-flow)
- [MQTT namespace and topics](#mqtt-namespace-and-topics)
- [Profiles](#profiles)
- [Widget types and capabilities](#widget-types-and-capabilities)
- [Protected actions](#protected-actions)
- [Notifications](#notifications-ha--ipad-popup)
- [Device settings and persistence](#device-settings-and-persistence)
- [Developer overlay](#developer-overlay)
- [Troubleshooting](#troubleshooting)
- [Complete parameters reference](#complete-parameters-reference)
 - [How to report issues](#how-to-report-issues)

## Supported devices
The dashboard app is provided as Debian packages and supports the following iPad families. Choose the .deb variant that matches your device/OS (see Installation below).

- Legacy (32‑bit, armv7 — iOS 5.1.1 up to 10.3.x):
    - iPad (1st gen) — iOS 5.1.1
    - iPad 2 — up to iOS 9.3.5
    - iPad (3rd gen) — up to iOS 9.3.6
    - iPad (4th gen) — up to iOS 10.3.3
    - iPad mini (1st gen) — up to iOS 9.3.5

- Modern (64‑bit, arm64 — iOS 12.0 or later):
    - iPad Air (1st gen), iPad Air 2
    - iPad mini 2, mini 3, mini 4
    - iPad (5th gen 2017), iPad (6th gen 2018)
    - iPad Pro 12.9 (1st/2nd gen), iPad Pro 9.7, iPad Pro 10.5

Notes:
- 32‑bit devices use the legacy package and run from iOS 5.1.1 through their final supported iOS version.
- 64‑bit devices require iOS 12 or newer for the modern package.
- A universal .deb is also provided that contains both architectures; the device installs the appropriate binary automatically.

## Installation
Install the provided .deb on your jailbroken iPad using your preferred package manager (Sileo/Cydia/Zebra) or via dpkg/SSH. Packages are offered in three variants:

- Universal: includes both armv7 (legacy) and arm64 (modern)
- Legacy: armv7 only (for iPad 1 and other 32‑bit models)
- Modern: arm64 only (for 64‑bit iPads on iOS 12+)

After installation, open the app and enter your MQTT broker details. Then proceed with the Home Assistant integration setup below.

## Quick start: minimal profile
Add a device in the integration, then use a simple profile like this to see tiles immediately:

```json
{
    "banner": "Main Panel",
    "grid": { "columns": 6, "widget_dimensions": [120,120], "widget_margins": [5,5], "widget_size": [1,1] },
    "widgets": [
        { "type": "light",  "entity_id": "light.living", "label": "Living", "x": 0, "y": 0, "w": 2, "h": 1 },
        { "type": "sensor", "entity_id": "sensor.outdoor_temp", "label": "Outside", "unit": "°C", "x": 2, "y": 0 },
        { "type": "switch", "entity_id": "switch.kettle", "label": "Kettle", "protected": true, "x": 3, "y": 0 },
        { "type": "clock",  "label": "Time", "time_pattern": "HH:MM", "x": 4, "y": 0 },
        { "type": "weather", "entity_id": "weather.home", "label": "Weather", "attrs": ["temperature","humidity"], "attr_units": {"temperature":"°C","humidity":"%"}, "x": 5, "y": 0, "w": 2 }
    ]
}
```

Widget examples quick links:
- [Light example](#light-with-brightness-and-colors)
- [Sensor example](#sensor-with-unit-and-alignment)
- [Switch (protected) example](#protected-switch-fulltile-with-colors)
- [Clock example](#clock-widget)
- [Weather example](#weather-widget-attributes-with-units)

## Home Assistant integration overview
- The custom component publishes retained device configurations for each registered device ID.
- Entity states and selected attributes are mirrored (retained) for fast rehydrate on the device.
- Widgets publish stateless JSON command payloads; the integration handles routing.
- Device settings and presence are exchanged via retained/non‑retained messages managed by the integration.

Presence and reconnects:
- Each device publishes retained online/offline status via MQTT Last Will at `mqttdash/dev/<device_id>/status`.
- Clients reconnect with exponential backoff and re‑subscribe to all topics; UI rehydrates instantly from retained messages.

Services (examples):
- push_config, set_device_settings, publish_snapshot.

## Device provisioning and config flow
1. App boots, sends hello, subscribes to its retained config topic.
2. HA integration publishes (or republishes) config. App renders grid.
3. Device settings retained message applies brightness/orientation/keep-awake.
4. On profile save in HA, the integration sends a non‑retained reload and republishes retained config.

## Messaging contract (high-level)

## MQTT namespace and topics
Fixed namespace (no custom bases):
- Configs (retained): `mqttdash/config/<device_id>/config`
- Device topics:
    - Settings (retained): `mqttdash/dev/<device_id>/settings`
    - Hello (non‑retained): `mqttdash/dev/<device_id>/hello`
    - Status/LWT (retained): `mqttdash/dev/<device_id>/status` (online/offline)
    - Notify (non‑retained): `mqttdash/dev/<device_id>/notify`
- Commands (non‑retained): `mqttdash/cmd/<entity_id>`
- Statestream (retained):
    - State: `mqttdash/statestream/<domain>/<object>/state`
    - Attributes: `mqttdash/statestream/<domain>/<object>/attributes[/<key>]`

The integration auto-wires all widget topics under the fixed namespace. Profiles never include MQTT topics.

## Profiles
The profile defines the device UI and is persisted in HA Store. The integration generates device config from the profile.

### Profile creation guide
- What is a profile? It defines the UI layout and widgets for a dashboard client. Each device references a profile; the integration publishes a per‑device config derived from the profile.
- Storage model: Profiles may be stored as a JSON object keyed by profile name (often the device_id). If wrapped like `{ "<name>": { ... } }`, the integration unwraps automatically.
- Device settings: Keep‑awake, brightness, and orientation are not part of profiles. They’re exposed as HA entities and sent to the app via the device settings topic.
- Topics: Do not include MQTT topics in profiles. The integration auto‑generates `state_topic`, `attr_topic` (e.g., brightness for lights), and `command_topic` from `entity_id` and widget `type`.
- Layout shorthands: Positioning aliases like `x`/`y` and `w`/`h` are supported (also `row`/`col` and `rowspan`/`colspan`). See Formatting and Widget sections below for supported keys.
- Examples: See the “Widget configuration examples” section for sensor, light, label, clock, and weather examples.

### Profiles — quick reference
- Grid keys (in `ui.grid`):
    - `columns`, `widget_dimensions` [w,h], `widget_margins` [x,y], `widget_size` [w,h], `devOverlay`
- Layout aliases:
    - Position `x|col`, `y|row`; Span `w|colspan`, `h|rowspan`
- Widgets (in `ui.widgets`):
    - Common: `id`, `type`, `entity_id`, `label`, `x`, `y`, `w`, `h`, `format`, `protected`
    - Type-specific extras:
        - light: auto `attr_topic` for brightness when mirrored
        - label: `text`
        - clock: `time_pattern`
        - weather: `attrs`, `attr_units`, auto `attr_base`
- Formatting keys (whitelist):
    - `align`, `vAlign`, `textSize`, `textColor`, `bgColor`, `onTextColor`, `offTextColor`, `onBgColor`, `offBgColor`, `wrap`, `maxLines`

Grid (in `ui.grid`):
- `columns`: number of columns
- `widget_dimensions`: [width, height] of a single cell in points
- `widget_margins`: [marginX, marginY] in points
- `widget_size`: [cellW, cellH] default widget span
- `devOverlay`: boolean to show grid indices overlay (authoring aid)

Widgets (in `ui.widgets`): Each widget supports `id`, `type`, `entity_id`, `label`, `x`, `y`, `w`, `h`, and optional `format`.

Common optional field for actionable widgets (light/switch/scene/button):
- `protected`: true|false — requires swipe‑to‑confirm before sending a command.

Formatting (`format`):
- Common: `align` (left|center|right), `vAlign` (top|middle|bottom), `textSize` (points), `textColor`, `bgColor`.
- State-aware (lights/switches/scenes/buttons): `onBgColor`, `offBgColor`, `onTextColor`, `offTextColor`.
- Text wrapping: `wrap` (true|false) and `maxLines` (integer) enable multi‑line labels and sensor text.
- Notes: Unsupported keys are ignored. Formatting is client-side only.

## Widget types and capabilities
- light: On/off; optional brightness slider when attributes are mirrored. Supports align, vAlign, textSize, on/off colors, and protected.
- switch: On/off as a full‑tile stateful button (no tiny UISwitch). Supports align, vAlign, textSize, on/off colors, and protected.
- scene: Stateless trigger; can reflect active state by color if mirrored. Supports align, vAlign, textSize, on/off colors, and protected.
- sensor/value: Shows value and optional unit (unit renders at 0.5x). Supports align, vAlign, textSize, textColor, bgColor, wrap/maxLines.
- person: Same as sensor.
- button: Stateless press; supports align, vAlign, textSize, textColor, bgColor, and protected.
- label: Static text only; supports align, vAlign, textSize, textColor, wrap/maxLines; tile background uses bgColor.
- clock: Local device time; no entity required. Optional `time_pattern` like `HH:MM:SS`, `HH:MM`, or custom tokens.
- weather: For `weather.*` entities. Provide `attrs` (list of attribute keys to show). Optional `attr_units` maps key→unit string. Integration supplies `attr_base` for MQTT subscriptions. The client has sensible default units for common keys (e.g., humidity %, pressure hPa).

Notes:
- Actionable widgets (light/switch/scene/button) support `protected: true` to require swipe‑to‑confirm.
- For lights, `attr_topic` for brightness is auto‑injected.

Tips
- Use valid JSON and the integration’s editor when possible.
- Give each device its own profile (often keyed by device_id) to keep layouts distinct.
- If the app’s hello includes screen details (width/height/scale), the integration echoes them under `device.screen` in the device config to help you tune grid sizes and widget dimensions.

## Device settings and persistence
- Retained device settings include brightness (0..1 clamped), keepAwake, orientation (auto|portrait|landscape). App applies on load.
- HA Store is canonical for profiles and per-device settings.

## Developer overlay
- Set `devOverlay` to true under `ui.grid` to draw a faint grid and x,y labels (x=column, y=row). Overlay is fully pass‑through and does not block touches.

## Troubleshooting
- Connection churn: keepalive 30s; connect timeout 12s; exponential backoff with jitter; check broker listeners (plain MQTT TCP, not WS/TLS, not v5‑only).
- Unexpected publishes: app logs all publishes; soft-suppresses if no recent user touch; dedup within 2 seconds.
- CONNACK rc not in 0..5: indicates protocol mismatch or previously a parser misalignment; fixed. Ensure MQTT 3.1.1 listener is used.

For detailed HA integration behavior and admin services, see `ha_mqtt_dash/ha_mqtt_dash` and the code comments.


## Commands and payloads
Examples of command payloads (non‑retained):
- `{ "action": "turn_on" }`
- `{ "action": "turn_off" }`
- `{ "action": "press" }`
- `{ "action": "turn_on", "brightness": 180 }`

Admin/service commands (via HA helpers):
- `{ "action": "snapshot" }`

## Notifications (HA → iPad popup)
- Domain service: `ha_mqtt_dash.notify` with fields: `device_id` (or `ha_device` via device selector), `message` (required), `title` (optional).
- Per-device services: dynamic `notify.mqttdash_<device_id>` (hyphens become underscores). Fields: `message` (required), `title` (optional).
Behavior: Publishes a non‑retained JSON payload to `mqttdash/dev/<device_id>/notify`. The iPad shows a popup banner with sound/vibrate.

## Retention policy
- Retained: device configs, device status/hello reflection, device settings, mirrored entity states and attributes.
- Non‑retained: device requests (e.g., reload, snapshot) and entity command messages.

## Mirroring vs. profile behavior

Behavior summary and notes:
- The backend publishes to MQTT only when values change; on HA startup and on explicit snapshot requests, a retained snapshot is sent so devices can rehydrate instantly.
- To show a mirrored entity on a device, add a widget for it in the profile by specifying `entity_id`, `type`, and layout (`x,y,w,h`). The integration injects the correct MQTT topics into the device config automatically.


Connectivity notes:
- The app speaks MQTT 3.1.1 (protocol level 4) over plain TCP. Ensure your broker listener matches (e.g., Mosquitto `protocol mqtt` on port 1883). MQTT v5-only or WebSockets/TLS-only listeners are not supported by this client.

Presence in HA:
- Each configured device exposes a `binary_sensor` for connectivity reflecting the device’s MQTT Last Will status. The app publishes retained `online` to `mqttdash/dev/<device_id>/status` on connect, and the broker sets `offline` on disconnect via LWT. This provides an immediate, retained online/offline indicator in Home Assistant.
3. App renders the grid and applies device settings (brightness/orientation/keepAwake).
4. User actions publish JSON commands (non‑retained).
5. On profile save, integration sends a `reload` device request (non‑retained) and republishes retained config.

## Menu and logs access
- Open menu: Long‑press anywhere outside widgets. A menu appears with “View Logs”, “Toggle Dev Overlay”, and “Settings”.
- Toggle dev overlay: Use the “Toggle Dev Overlay” menu item.
- Note: There are no on‑screen menu/logs buttons anymore.

## CONNACK errors and tips
- 0 (Connection Accepted): OK.
- 1 (Unacceptable protocol version): Use MQTT 3.1.1 listener.
- 2 (Identifier rejected): Check client ID uniqueness.
- 3 (Server unavailable): Broker down or listener blocked.
- 4 (Bad username or password): Fix credentials in Settings.
- 5 (Not authorized): Check your broker ACLs permit the dashboard’s topics.
- Other values (e.g., 58/0x3A): For non‑spec values, ensure the broker isn’t MQTT v5‑only and that a 3.1.1 TCP listener is enabled. The app’s MQTT parser was hardened to handle fragmented frames and QoS>0 packet identifiers.

## Widget configuration examples
Light with brightness and colors:
```json
{
    "id": "w1",
    "type": "light",
    "entity_id": "light.living_room",
    "label": "Living Room",
    "x": 0,
    "y": 0,
    "w": 1,
    "h": 1,
    "format": {
        "align": "left",
        "vAlign": "bottom",
        "textSize": 20,
        "onBgColor": "#145214",
        "offBgColor": "#222",
        "onTextColor": "#fff",
        "offTextColor": "#ddd"
    }
}
```

Sensor with unit and alignment:
```json
{
    "id": "t1",
    "type": "sensor",
    "entity_id": "sensor.outdoor_temp",
    "unit": "°C",
    "label": "Outside",
    "x": 1,
    "y": 0,
    "w": 1,
    "h": 1,
    "format": {
        "align": "right",
        "vAlign": "top",
        "textSize": 24,
        "textColor": "#8ad"
    }
}
```

Button and scene:
```json
{
    "id": "b1",
    "type": "button",
    "label": "Doorbell",
    "x": 0,
    "y": 1,
    "w": 1,
    "h": 1,
    "format": {
        "bgColor": "#222",
        "textColor": "#fff"
    }
}
{
    "id": "s1",
    "type": "scene",
    "entity_id": "scene.movie_night",
    "label": "Movie Night",
    "x": 1,
    "y": 1,
    "w": 1,
    "h": 1,
    "format": {
        "onBgColor": "#334",
        "offBgColor": "#111"
    }
}
```

Protected switch (full‑tile) with colors:
```json
{
    "id": "sw1",
    "type": "switch",
    "entity_id": "switch.kettle",
    "label": "Kettle",
    "protected": true,
    "x": 2,
    "y": 1,
    "w": 1,
    "h": 1,
    "format": {
        "onBgColor": "#2E7D32",
        "offBgColor": "#263238",
        "onTextColor": "#FFFFFF",
        "offTextColor": "#B0BEC5"
    }
}
```

Clock widget:
```json
{
    "id": "clk1",
    "type": "clock",
    "label": "Time",
    "time_pattern": "HH:MM:SS",
    "x": 3, "y": 0, "w": 1, "h": 1
}
```

Weather widget (attributes with units):
```json
{
    "id": "wx1",
    "type": "weather",
    "entity_id": "weather.home",
    "label": "Weather",
    "attrs": ["temperature", "humidity", "wind_speed"],
    "attr_units": { "temperature": "°C", "humidity": "%", "wind_speed": "km/h" },
    "x": 4, "y": 0, "w": 2, "h": 1
}
```

## Grid configuration notes

## Integration setup (Home Assistant)
1. Install the `ha_mqtt_dash` custom component.
2. Configure MQTT in HA with a TCP listener and Statestream enabled as needed by the integration.
3. In HA, add the MQTT Dashboard integration and create a profile describing your UI.
4. Add a device with a `device_id` and assign the profile. The integration publishes a retained config for that device.
5. Optionally set per‑device settings (brightness/orientation/keepAwake). These are retained.

## Credentials and prerequisites
- Broker: MQTT 3.1.1 over TCP on your LAN. No TLS/WebSockets required.
- ACLs: Restrict access to the dashboard’s MQTT topics per device according to your broker’s best practices.
- iPad app: Set broker host/port and credentials in Settings on first run.

## Add or remove a device
- Add: In HA, create a new device, assign a profile, and power on the iPad app with that device ID. The app will fetch retained config and render immediately.
- Rename: Change the name on the device; the app includes a stable GUID in hello, and the integration will migrate the device_id automatically when it sees the GUID/prev_id.
- Remove: Use Home Assistant's built-in "Delete device". The integration purges retained MQTT topics and cleans up registries.

## Complete parameters reference

This section documents all supported parameters in profiles and the generated device config. The integration normalizes profiles into a config document with this shape:

Top-level (published to `mqttdash/config/<device_id>/config`):
- `version`: number — config schema version (currently 1)
- `device_id`: string — target device ID
- `device`: object — may include `screen` info (from device hello). Not used for settings.
- `ui`: object — grid and widgets (see below)
- `topics`: object — device topics
    - `settings`: string — `mqttdash/dev/<device_id>/settings` (retained)
    - `hello`: string — `mqttdash/dev/<device_id>/hello`
    - `status`: string — `mqttdash/dev/<device_id>/status` (retained LWT online/offline)

Profile inputs accepted (before normalization):
- Top-level or under `ui`:
    - `grid`: object — see UI Grid
    - `columns` | `cols`: number — columns count (alias to `ui.grid.columns` when using `dashboard.layout`)
    - `layout`: array — HADashboard-like layout rows (strings or arrays) used with `columns`
    - `widgets`: array — explicit widgets
- Wrapper: If a profile is wrapped as `{ "<name>": { ... } }`, it is unwrapped.

UI Grid (final form in `ui.grid`):
- `columns`: number — required when using `layout`; optional otherwise
- `widget_dimensions`: [widthPts, heightPts] — default [120,120]
- `widget_margins`: [marginX, marginY] — default [5,5]
- `widget_size`: [cellW, cellH] — default [1,1]
- `devOverlay`: boolean — show grid indices overlay (authoring aid)

Dashboard layout (optional):
- `columns` or `cols`: number — grid width
- `layout`: array of rows, each row can be:
    - string with comma-separated items, e.g. `"light.kitchen, sensor.temp, light.living(2x1), spacer"`
    - array of items `["light.kitchen", "sensor.temp"]`
    - object `{ "empty": N }` to skip N rows
- Item syntax:
    - `domain.object` (e.g., `light.kitchen`)
    - `domain.object(WxH)` to set span (e.g., `light.living(2x1)`)
    - `spacer` to skip a cell

Widgets (accepted input fields before normalization):
- `id`: string — optional; autogenerated if missing
- `type`: string — one of: `light`, `switch`, `scene`, `sensor`, `value`, `person`, `button`, `label`, `clock`, `weather`, `spacer`
- `entity_id` | `entity` | `eid`: string — entity id (not required for `label`/`clock`)
- `label` | `lbl`: string — display label; defaults to `entity_id`
- Position and span (aliases accepted):
    - `x` | `col`: number (default 0)
    - `y` | `row`: number (default 0)
    - `w` | `colspan`: number (min 1; default 1)
    - `h` | `rowspan`: number (min 1; default 1)
- `unit`: string — for `sensor`/`value`
- `format`: object — formatting options (whitelisted keys only; see below)
- `protected`: boolean — for actionable widgets (light/switch/scene/button) to require swipe-to-confirm
- `text`: string — only for `label` (no entity)
- `time_pattern`: string — only for `clock` (no entity)
- Weather-specific:
    - `attrs`: array of strings — attribute keys to display (e.g., `temperature`, `humidity`, `wind_speed`)
    - `attr_units`: object — map of key→unit string (optional; app has defaults)

Widget normalization (final form):
- All widgets include:
    - `id`, `type`, `entity_id`, `label`, `x`, `y`, `w`, `h`
    - `unit`: if provided
    - `format`: only keys in { `align`, `vAlign`, `textSize`, `textColor`, `bgColor`, `onTextColor`, `offTextColor`, `onBgColor`, `offBgColor`, `wrap`, `maxLines` }
    - `protected`: if provided and boolean
- Light extras:
    - `attr_topic`: `mqttdash/statestream/light/<object>/attributes/brightness`
- Label extras:
    - `text`: provided text
- Clock extras:
    - `time_pattern`: if provided
- Weather extras:
    - `attr_base`: `mqttdash/statestream/weather/<object>/attributes`
    - `attrs`: list of keys (if provided)
    - `attr_units`: map of key→unit (if provided)

Formatting keys (`format`):
- `align`: `left` | `center` | `right`
- `vAlign`: `top` | `middle` | `bottom`
- `textSize`: number (points)
- `textColor`: hex string
- `bgColor`: hex string
- `onTextColor`, `offTextColor`: hex strings
- `onBgColor`, `offBgColor`: hex strings
- `wrap`: boolean — enable multi-line wrapping
- `maxLines`: number — maximum lines to display (when `wrap` true)

Device hello payload (app → HA on `mqttdash/dev/<id>/hello`):
- JSON with optional fields:
    - `guid`: string — stable unique identifier for device instance
    - `prev_id`: string — previous device_id to support seamless rename/migration
    - `screen`: object — as provided by the client, persisted and echoed back under `device.screen` in config

Device status (presence):
- `mqttdash/dev/<id>/status`: retained `online`/`offline` via MQTT LWT

Commands (app → HA via integration):
- Published by the app to `mqttdash/cmd/<entity_id>` with JSON payloads:
    - `{ "action": "turn_on" }`
    - `{ "action": "turn_off" }`
    - `{ "action": "press" }`
    - Lights can include `{ "brightness": 0..255 }`

Device settings (HA → app):
- `mqttdash/dev/<id>/settings` (retained) JSON fields (all optional; app applies if present):
    - `brightness`: number 0..1 (clamped)
    - `keep_awake`: boolean
    - `orientation`: `auto` | `portrait` | `landscape`

Mirroring configuration (in integration options):
- `mirror_entities`: array of `domain.object` strings
- Behavior:
    - Retained state at `mqttdash/statestream/<domain>/<object>/state`
    - Retained attributes at `mqttdash/statestream/<domain>/<object>/attributes/<key>`
    - Snapshot publishes full states/attributes: auto at HA startup and on demand via service
    - Dedupe avoids redundant publishes; removed attributes are purged by sending empty retained values

Admin/services (HA → integration):
- `ha_mqtt_dash.push_config` — republish retained configs for all devices
- `ha_mqtt_dash.reload_config` — send reload then republish configs
- `ha_mqtt_dash.set_device_settings` — send settings to a device
- `ha_mqtt_dash.publish_snapshot` — publish snapshot for mirrored entities
- `ha_mqtt_dash.set_device_profile` — overwrite a device’s profile JSON in HA Store and republish
- `ha_mqtt_dash.dump_store` — log/publish Store JSON
- `ha_mqtt_dash.dump_runtime_cfg` — log/publish merged runtime cfg
- `ha_mqtt_dash.republish_reload_all` — convenience to trigger reload+republish cycle
- `ha_mqtt_dash.prune_unassigned` — remove unassigned devices and purge retained topics
- Notifications:
    - Domain service `ha_mqtt_dash.notify` — fields: `device_id` (or `ha_device`), `message` (required), `title` (optional)
    - Per-device services under `notify` domain: `notify.mqttdash_<device_id>` — fields: `message`, `title`

Notes and edge cases:
- Profiles must not include MQTT topic fields; the integration injects them.
- Unknown `type` or missing `entity_id` (except for `label`/`clock`) are skipped.
- `spacer` widgets are ignored in normalization; use layout `spacer` entries when needed.
- When a device is removed from options, the integration purges its retained config/settings.
- On profile save, a `reload` is sent first (non-retained), followed by republished retained config.

## How to report issues

Please see the issue reporting guide and template here:

- [ISSUE_REPORTING.md](./ISSUE_REPORTING.md)

It includes a step-by-step checklist, what logs and MQTT captures to attach, and a copy-paste template to make triage fast.
