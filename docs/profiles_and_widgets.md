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

## Panel settings

Keep awake, brightness, screensaver timeout and orientation are not part of a profile. They are Home Assistant entities on the panel's device (see [Installation](installation.md#per-panel-entities)); a `device` block in a profile is ignored.

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
Tap toggles. **Drag up/down on the card to set brightness** (left/right on wide cards); the card fills to the brightness level and releasing sends it (drag to 0 turns the light off). Dimmability is detected from the light's `supported_color_modes`, so on/off-only lights just toggle; `dimmable: false` forces on/off only.

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
For `climate.*` entities. Big current temperature, a −/+ target stepper (taps update the card instantly and are sent once you pause; values are clamped to the entity's `min_temp`/`max_temp`), an `hvac_action` chip (Heating / Idle) and mode pills. Optional `modes` limits selectable HVAC modes; `state_formats` colors each mode (its `bgColor` tints the card and pill). Optional `temp_step` (e.g. `0.5`); default is the entity's `target_temp_step`, but at least 0.5. On 1-wide cards, tap the chip to cycle modes.

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

Commands published: `set_hvac_mode`, `set_temperature`. The integration auto-injects `attr_base`.

**`camera`**
Two sources:

- `camera_entity` (recommended) — any HA `camera.*` entity. HA grabs frames and relays them as JPEGs over MQTT, so it works for cameras the iPad can't play (WebRTC/go2rtc, HTTPS, token-protected). Frames are only produced while a device is actually showing the camera.
- `stream_url` — a plain-HTTP MJPEG stream or a JPEG snapshot URL, fetched directly by the iPad.

`refresh_interval` sets seconds between frames (default 1 for `camera_entity`). Tap the image for full screen; ↺ reconnects. Streaming stops when the page is hidden, the screensaver is up or the screen is off. Optional `overlay_button` places an action button at the bottom-right:

```json
{
  "type": "camera",
  "camera_entity": "camera.k1c_printer_camera",
  "overlay_button": {
    "label": "Door",
    "action": "press",
    "entity_id": "script.open_door"
  }
}
```

Optional `scale_mode`: `"fit"` or `"fill"` / `"stretch"`.

**`printer` / `printer3d`**
Composite widget for 3D printers. Binds to multiple entity IDs — mix and match what you have.

| Field | Description |
|-------|-------------|
| `nozzle_entity` | Nozzle temperature sensor |
| `bed_entity` | Bed temperature sensor |
| `time_entity` | Time remaining (unit-aware: h / min / s, `H:MM:SS`, or an end timestamp) |
| `progress_entity` | Progress percentage sensor |
| `status_entity` | Status text sensor (its `file` attribute is shown as the job name) |
| `nozzle_target_entity` / `bed_target_entity` | Target temperatures, shown as `224/225°` |
| `layer_entity` / `total_layers_entity` | Current / total layer |
| `preview_entity` | `image.*` entity with the print thumbnail (relayed by HA) |
| `progress_unit` | Unit string (e.g., `"%"`) |
| `visible_rows` | Subset of `nozzle`, `bed`, `time`, `progress`, `status`, `preview`, `layer` |

Shows status chip, big progress, time left + ETA, and a stats row.

**`timer`**
Local countdown timer — no entity or MQTT required. State persists across page switches.

| Field | Default | Description |
|-------|---------|-------------|
| `default_seconds` | 300 | Starting duration |
| `configurable` | true | `false` = fixed duration: long-press resets instead of opening the picker |
| `presets` | 1–60 min | Quick-pick durations (seconds) shown in the picker |

Tap to start / pause / stop the alarm. **Long-press opens the time picker**: preset chips, recent durations, ±10 s / ±1 min, **Start**, and **Save as default**, which remembers the duration for that timer on the device. A paused timer shows ↺ to reset. Timers keep running across config reloads and app restarts, keep the screen awake while active, and bring their page to the front when the alarm rings.

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
| `time_entity` | Time remaining (unit-aware) |
| `unit` | Temperature unit (default `°C`) |

The entities are mirrored automatically.

**`appliance`**
Washer / dishwasher / any appliance (works great with WashData). Shows a state chip (Running, Paused, Finished, Anti wrinkle…), time remaining, program · phase, "Done ~21:07", and a progress bar.

| Field | Description |
|-------|-------------|
| `entity_id` | State sensor or on/off binary sensor |
| `program_entity` | Current program name sensor |
| `time_entity` | Time remaining (unit-aware) |
| `progress_entity` | 0–100 % sensor (optional) |
| `phase_entity` | Current phase / sub-state (optional) |

If `progress_entity` / `phase_entity` are omitted and `time_entity` is `sensor.<x>_time_remaining`, HA uses `sensor.<x>_progress` / `sensor.<x>_current_phase` when they exist.

The entities are mirrored automatically.

**`mediaplayer`**
Media player for any `media_player.*` entity; the integration adds the MQTT topics. Works at any size from one cell to full screen:

- **Art** (fetched and relayed by HA; `show_art: false` turns it off) goes beside the text on wide cards when it fills the card's height, across the top on tall ones, and dimmed behind everything on small ones.
- The rest of the card gets, while they fit: title and artist, transport, a header with the name and the **output picker**, a seek bar with times, and volume. Leftover space makes the text and buttons larger. A card too small for a seek bar shows a thin progress line along its bottom edge.
- Controls follow the player's `supported_features`: shuffle and repeat, prev/next, seek, volume, mute and output appear only when the player has them. The layout updates when they change (e.g. another Spotify device).
- **Output** is the player's `source_list` (Spotify Connect devices, receiver inputs); tap to pick where it plays.
- **Long-press** the card for the full-screen player with every control.

State `playing` shows pause; `off`/`unavailable`/`unknown` dims the card, and an off player that supports it shows a power button.

Commands: `media_play_pause`, `media_next_track`, `media_previous_track`, `media_seek` (`position` in seconds), `volume_set` (`volume_level` 0–1), `volume_mute` (`is_volume_muted`), `select_source` (`source`), `shuffle_set` (`shuffle`), `repeat_set` (`repeat`: off / all / one), `turn_on`.

The entity is mirrored automatically.

**`cover`**
For `cover.*` entities (blinds, shades, garage doors, RF shades). The controls shown on the tile **adapt to the entity's `supported_features`**, so a simple open/close-only device shows two buttons while a positionable, tilting blind shows the full set:

- **Open (▲) / Close (▼)** — always shown.
- **Stop (■)** — shown when the cover supports `STOP` (or when `supported_features` is not yet known).
- **Position slider** — shown when the cover supports `SET_POSITION`; reflects `current_position` (0 = closed, 100 = open) and publishes on release.
- **Tilt controls** — tilt open/close buttons and/or a tilt slider, shown when the cover advertises the corresponding tilt features.

The center label shows the state (`OPEN`/`CLOSED`/`OPENING`/`CLOSING`) and the current position percentage when available. Set `protected: true` to require a confirmation tap before open/close (recommended for garage doors); the stop button is never gated.

**Configurable controls (`cover_items`).** When omitted, controls are auto-detected from the entity's `supported_features`. To choose exactly which controls appear and in what order, set `cover_items` to an ordered array of any of these tokens:

| Token | Renders |
|-------|---------|
| `"open"` | Open button (▲) |
| `"close"` | Close button (▼) |
| `"stop"` | Stop button (■) |
| `"position"` | Position slider (0–100) |
| `"presets"` | A row of position-preset buttons (see `position_presets`) |
| `"tilt_open"` | Tilt-open button (drawn slat icon) |
| `"tilt_close"` | Tilt-close button |
| `"tilt_slider"` | Tilt position slider |

The **order** of the array is honored: top→bottom in tall tiles, row sequence in wide tiles. Controls are **elastic** — `cover_layout` (`"auto"` \| `"horizontal"` \| `"vertical"`) sets orientation; `"auto"` picks from the tile's aspect ratio. In vertical layout, sliders render as **upright (vertical) sliders** beside a button column so they keep full travel in tall tiles. `position_presets` is an array of percentages (default `[0, 25, 75, 100]`) used when `presets` is included.

```json
{
  "type": "cover",
  "entity_id": "cover.bedroom_blinds",
  "label": "Bedroom",
  "protected": false,
  "cover_items": ["position", "presets", "open", "stop", "close"],
  "cover_layout": "auto",
  "position_presets": [0, 25, 75, 100]
}
```

> The earlier coarse `cover_controls` array (`"buttons"`/`"slider"`/`"presets"`/`"tilt"`) is still accepted for backward compatibility and is expanded into the equivalent `cover_items` tokens.

Commands published: `open_cover`, `close_cover`, `stop_cover`, `set_cover_position` (with `position` 0–100), and the tilt equivalents `open_cover_tilt`, `close_cover_tilt`, `set_cover_tilt_position`. The integration auto-injects `attr_base`; the app reads `current_position`, `current_tilt_position`, and `supported_features` from it.

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
