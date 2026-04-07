# Profiles and widgets

Profiles define the device UI and are stored in Home Assistant's persistent storage. Each device has its own profile keyed by `device_id`.

## Profile structure

A profile is a JSON object with the following top-level keys:

```json
{
  "ui": {
    "grid": { ... },
    "pages": [ ... ],
    "widgets": [ ... ],
    "navbar_edge": "bottom",
    "navbar_style": { ... },
    "navbar_show_battery": true,
    "navbar_show_keep_awake": true
  },
  "device": {
    "keepAwake": false,
    "brightness": 0.8,
    "orientation": "auto",
    "screensaverTimeout": 120,
    "screensaverFontSize": 0
  }
}
```

If a pasted profile is wrapped like `{ "<name>": { ... } }`, the integration unwraps it automatically.

Do not include MQTT topics in profiles. The integration injects `state_topic`, `attr_topic`, `command_topic`, and all other MQTT wiring based on the entity IDs.

Layout shorthands supported: `x|col`, `y|row`, `w|colspan`, `h|rowspan`.

---

## Grid (`ui.grid`)

Applied globally unless overridden per page.

- `columns` — number of columns
- `widget_dimensions` — `[width, height]` of a single cell in points
- `widget_margins` — `[marginX, marginY]` in points
- `widget_size` — `[cellW, cellH]` default widget span
- `devOverlay` — `true` to draw a faint grid with x,y labels (authoring aid; pass-through, does not block touches)

---

## Multi-page layouts (`ui.pages`)

Profiles support either a flat `widgets` array (single page, legacy) or a `pages` array (multi-page). Both are supported simultaneously for backwards compatibility.

```json
"pages": [
  {
    "name": "Bedroom",
    "widgets": [ ... ],
    "grid": { "columns": 4 }
  },
  {
    "name": "Living Room",
    "widgets": [ ... ]
  }
]
```

- Each page has a `name`, a `widgets` array, and an optional `grid` override.
- Navigation shows a tab bar (default: bottom) with named page buttons.
- Swipe left/right to switch pages.
- All pages are pre-rendered and all receive live MQTT state updates regardless of which page is active.

---

## Navigation bar

**`ui.navbar_edge`** — placement of the tab bar: `"top"` | `"bottom"` | `"left"` | `"right"` (default `"bottom"`)

**`ui.navbar_show_battery`** — show/hide the battery indicator (default `true`)

**`ui.navbar_show_keep_awake`** — show/hide the Keep-Awake toggle button (default `true`)

**`ui.navbar_style`** — optional object controlling bar appearance (all keys optional):

| Key | Default | Description |
|-----|---------|-------------|
| `bgColor` | `#141414` | Bar background |
| `activeColor` | `#336ee6` | Active page button background |
| `inactiveColor` | `#404040` | Inactive page button background |
| `textColor` | `#ffffff` | Button label text |
| `borderColor` | `rgba(255,255,255,0.18)` | Separator line |

Example:
```json
"navbar_style": {
  "bgColor": "#0d1117",
  "activeColor": "#238636",
  "inactiveColor": "#21262d",
  "textColor": "#f0f6fc"
}
```

---

## Device settings (`device`)

These mirror the HA entities created for each device and are applied on load and reconnect.

| Key | Type | Description |
|-----|------|-------------|
| `keepAwake` | boolean | Prevent screen from sleeping |
| `brightness` | number 0..1 | Screen brightness |
| `orientation` | string | `"auto"` \| `"portrait"` \| `"landscape"` |
| `screensaverTimeout` | number | Idle seconds before screensaver (0 = disabled) |
| `screensaverFontSize` | number | Screensaver clock font size in pt (0 = device default) |

These can also be set via the corresponding HA entities or the `ha_mqtt_dash.set_device_settings` service.

---

## Widgets

### Common fields (all widget types)

| Field | Notes |
|-------|-------|
| `id` | Optional; auto-generated if missing |
| `type` | Widget type (see below) |
| `entity_id` \| `entity` \| `eid` | Entity reference (not required for `label`, `clock`, `timer`, `webpage`) |
| `label` \| `lbl` | Display label; defaults to `entity_id` |
| `x` \| `col` | Column position (default 0) |
| `y` \| `row` | Row position (default 0) |
| `w` \| `colspan` | Column span (min 1, default 1) |
| `h` \| `rowspan` | Row span (min 1, default 1) |
| `unit` | Unit string — for `sensor`, `value`, `sousvide` |
| `format` | Formatting object (see [Formatting](#formatting)) |
| `protected` | `true` to require swipe-to-confirm on actionable widgets |

---

### Widget types

**`light`**
On/off toggle with optional brightness slider. `attr_topic` for brightness is auto-injected from the entity ID. `dimmable: false` hides the slider.

**`switch`**
Full-tile stateful on/off button (not a UISwitch). Supports on/off colors and `protected`.

**`scene`**
Stateless trigger. Can reflect active state by color if the entity state is mirrored. Supports on/off colors and `protected`.

**`button`**
Stateless press button; no state. Supports `protected`.

**`sensor` / `value` / `person`**
Displays the entity state as text with an optional `unit` (rendered at half size). All three types render identically; `person` is a semantic alias.

**`label`**
Static text tile — no entity required. Set content via `text`. Supports `bgColor`, `textColor`, `align`, `vAlign`, `wrap`, `maxLines`.

**`clock`**
Displays local device time — no entity required. Optional `time_pattern` (e.g., `"HH:MM:SS"`, `"HH:MM"`).

**`weather`**
For `weather.*` entities. Provide `attrs` (array of attribute key strings) to select which attributes to display. Optional `attr_units` maps attribute keys to unit strings. The integration auto-injects `attr_base` for MQTT subscriptions.

```json
{
  "type": "weather",
  "entity_id": "weather.home",
  "attrs": ["temperature", "humidity", "wind_speed"],
  "attr_units": { "temperature": "°C", "humidity": "%", "wind_speed": "km/h" }
}
```

**`climate`**
For `climate.*` entities. Shows current and target temperature plus a mode selector segmented control. Optional `modes` limits selectable HVAC modes. Optional `state_formats` provides per-mode visual styling.

```json
{
  "type": "climate",
  "entity_id": "climate.living_room",
  "modes": ["off", "heat", "cool", "auto"],
  "state_formats": {
    "off":  { "bgColor": "#333333", "textColor": "#cccccc" },
    "heat": { "bgColor": "#ff6b35", "textColor": "#ffffff" },
    "cool": { "bgColor": "#0066ff", "textColor": "#ffffff" },
    "auto": { "bgColor": "#7b68ee", "textColor": "#ffffff" }
  }
}
```

Commands published: `set_hvac_mode`, `set_temperature`. The integration auto-injects `attr_base` and `extra_topics` for current and target temperature.

**`camera`**
Renders an MJPEG stream. `stream_url` is required. A refresh button (↺) is always shown at the top-right to reload the stream. Optional `overlay_button` places an action button at the bottom-right:

```json
{
  "type": "camera",
  "stream_url": "http://camera.local/mjpeg",
  "overlay_button": {
    "label": "Door",
    "action": "press",
    "entity_id": "script.open_door"
  }
}
```

Optional `scale_mode`: `"fit"` or `"fill"`.

**`printer` / `printer3d`**
Composite widget for 3D printers. Binds to multiple entity IDs — mix and match what you have.

| Field | Description |
|-------|-------------|
| `nozzle_entity` | Nozzle temperature sensor |
| `bed_entity` | Bed temperature sensor |
| `time_entity` | Time remaining (numeric minutes → displayed as HH:MM) |
| `progress_entity` | Progress percentage sensor |
| `status_entity` | Status text sensor |
| `progress_unit` | Unit string (e.g., `"%"`) |

**`timer`**
Local countdown timer — no entity or MQTT required. State persists across page switches.

| Field | Default | Description |
|-------|---------|-------------|
| `default_seconds` | 300 | Starting duration |
| `configurable` | true | `false` hides +/- buttons (repeat-only mode) |

Tap the time display to start/pause. Long-press to reset. +/- buttons adjust duration with accelerating repeat. When finished: 5 red flashes + vibration + alert sound.

**`webpage`**
Embeds any local URL in the tile. Set `stream_url` to the target URL. Uses WKWebView on iOS 8+ with automatic fallback to UIWebView on older iOS.

**`mealie`**
Connects to a self-hosted Mealie instance.

| Field | Description |
|-------|-------------|
| `mealie_url` | Base URL (e.g., `http://192.168.1.100:9000`) |
| `mealie_api_key` | Bearer token for the Mealie API |
| `recipe_slug` | Specific recipe slug to display; omit or `null` for the recipe picker |
| `visible_section` | `"ingredients"` \| `"steps"` \| `"both"` (default `"ingredients"`) |

**`sousvide`**
Sous vide cooker status tile. Dims when idle/off.

| Field | Description |
|-------|-------------|
| `entity_id` | Status sensor (`cooking` / `idle` / `off`) |
| `temp_entity` | Current temperature sensor |
| `target_entity` | Target temperature sensor |
| `time_entity` | Time remaining (numeric minutes → HH:MM) |
| `unit` | Temperature unit (default `°C`) |

All entities must be in `mirror_entities`.

**`appliance`**
Generic appliance status. Dims when off; program label shows "OFF".

| Field | Description |
|-------|-------------|
| `entity_id` | On/off switch or binary sensor |
| `program_entity` | Current program name sensor |
| `time_entity` | Time remaining (numeric minutes → HH:MM) |

All entities must be in `mirror_entities`.

**`mediaplayer`**
Media player with transport controls and progress bar. Point at any `media_player.*` entity — the integration auto-injects all required MQTT topics.

Displays: track title (2 lines), artist, ⏮ previous / ▶⏸ play-pause / ⏭ next, seekable progress bar with elapsed/total time.

State `playing` shows pause icon; `paused`/`idle` shows play; `off`/`unavailable`/`unknown` dims the tile.

Commands: `media_play_pause`, `media_next_track`, `media_previous_track`, `media_seek` (with `position` in seconds).

Entity must be in `mirror_entities`.

**`spacer`**
Empty placeholder. No entity, no label, no interaction — just an empty grid cell for layout spacing.

---

## Formatting

The `format` object accepts the following keys (unknown keys are silently dropped):

| Key | Type | Description |
|-----|------|-------------|
| `align` | string | `"left"` \| `"center"` \| `"right"` |
| `vAlign` | string | `"top"` \| `"middle"` \| `"bottom"` |
| `textSize` | number | Font size in points |
| `textColor` | hex string | Text color |
| `bgColor` | hex string | Tile background color |
| `onTextColor` | hex string | Text color when state is on/active |
| `offTextColor` | hex string | Text color when state is off/inactive |
| `onBgColor` | hex string | Background when state is on/active |
| `offBgColor` | hex string | Background when state is off/inactive |
| `wrap` | boolean | Enable multi-line text wrapping |
| `maxLines` | number | Maximum lines when `wrap` is true |

---

## Examples

**Light with brightness and on/off colors:**
```json
{
  "type": "light",
  "entity_id": "light.living_room",
  "label": "Living Room",
  "x": 0, "y": 0, "w": 1, "h": 1,
  "format": {
    "align": "left", "vAlign": "bottom",
    "textSize": 20,
    "onBgColor": "#145214", "offBgColor": "#222",
    "onTextColor": "#fff", "offTextColor": "#ddd"
  }
}
```

**Sensor with unit and alignment:**
```json
{
  "type": "sensor",
  "entity_id": "sensor.outdoor_temp",
  "label": "Outside",
  "unit": "°C",
  "x": 1, "y": 0, "w": 1, "h": 1,
  "format": { "align": "right", "vAlign": "top", "textSize": 24, "textColor": "#8ad" }
}
```

**Protected switch:**
```json
{
  "type": "switch",
  "entity_id": "switch.kettle",
  "label": "Kettle",
  "protected": true,
  "x": 2, "y": 1, "w": 1, "h": 1,
  "format": {
    "onBgColor": "#2e7d32", "offBgColor": "#263238",
    "onTextColor": "#ffffff", "offTextColor": "#b0bec5"
  }
}
```

**Clock:**
```json
{ "type": "clock", "label": "Time", "time_pattern": "HH:MM:SS", "x": 3, "y": 0, "w": 1, "h": 1 }
```

**Timer (fixed 10-minute, no adjustment):**
```json
{ "type": "timer", "label": "Eggs", "default_seconds": 600, "configurable": false, "x": 0, "y": 2, "w": 1, "h": 1 }
```

**Webpage:**
```json
{ "type": "webpage", "label": "Grafana", "stream_url": "http://grafana.local:3000/d/abc", "x": 0, "y": 3, "w": 3, "h": 2 }
```

**Media player:**
```json
{ "type": "mediaplayer", "entity_id": "media_player.living_room", "label": "Sonos", "x": 0, "y": 4, "w": 2, "h": 1 }
```

**3D printer composite:**
```json
{
  "type": "printer",
  "label": "Voron",
  "nozzle_entity": "sensor.nozzle_temp",
  "bed_entity": "sensor.bed_temp",
  "time_entity": "sensor.time_remaining_minutes",
  "progress_entity": "sensor.print_progress",
  "status_entity": "sensor.printer_status",
  "progress_unit": "%",
  "x": 0, "y": 5, "w": 2, "h": 1
}
```

**Camera with overlay button:**
```json
{
  "type": "camera",
  "label": "Porch",
  "stream_url": "http://camera.local/mjpeg",
  "overlay_button": { "label": "Door", "action": "press", "entity_id": "script.open_door" },
  "x": 2, "y": 5, "w": 2, "h": 2
}
```
