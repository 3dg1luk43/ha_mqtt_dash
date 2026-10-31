# Changelog

All notable changes to iPad MQTT Dashboard (integration, editor and the iPad app packages) are documented here.

---

## 0.6.0 - Unreleased

Redesigned cards, reliable reconnects, HA-relayed camera frames and album art, and a kiosk you can leave.

### iOS App
- **Fixed: dashboard froze on stale data** (e.g. heating not updating). A failed reconnect ended the retry loop; partial packets survived reconnects; dead Wi-Fi sockets went undetected; only one view per entity received updates. Reconnects now retry with backoff, restart instantly on wake, and an offline banner + nav dot show link state.
- **New card design** for every widget type in daily use: drawn icons, chips, progress bars, press feedback, optimistic updates.
- **Lights:** drag on the card to dim (fill shows the level); dimmability auto-detected from `supported_color_modes`.
- **Climate:** instant −/+ (debounced, clamped to min/max), `hvac_action` chip, mode pills, optional `temp_step`.
- **Timers:** long-press picker with presets, recents, fine adjust and **Save as default**; accurate end-time countdown that survives reloads/restarts; alarm brings its page forward. Running timers keep the screen awake.
- **Camera:** native MJPEG/snapshot client (no UIWebView) plus `camera_entity` frames relayed by HA; streams only while visible; tap for full screen.
- **Mealie:** new recipe grid (tag chips, pull or ↻ to refresh) and recipes that open inside the card (back arrow to the list), so timers and the rest of the dashboard stay usable while cooking: two columns on wide cards, tap ingredients to check off and steps to mark done (kept per recipe).
- **Printer / appliance / sous vide** redesigned; unit-aware durations with ETA; print thumbnail.
- **Media player** rebuilt as one fluid layout from a single cell to full screen: album art beside, above or behind the controls depending on the card's shape; title, transport, output picker, seek and volume added as space allows, with no empty areas. Controls follow the player's supported features (shuffle, repeat, volume, mute, output). Output picker lists the player's sources (e.g. Spotify Connect devices). Long-press opens the full-screen player.
- Identical configs are no longer re-rendered on reconnect; batched, de-duplicated subscriptions; Settings no longer pops up on network blips (auth failures only); "Exit to Home Screen" in the long-press menu.

- **Reachable while asleep:** with the screen off the app keeps a minimal VoIP-mode MQTT link (request topic only), so HA can wake it or read the battery; status reports `sleeping`. Toggle: Settings → Reachable asleep. HA's `sleep` request locks the screen again after a battery check (not while in use, keep-awake on or a timer runs). Lifecycle trace in `Library/Caches/mqttdash_life.log`.
- The sleep link is also set up when the app starts behind the lock screen (kiosk auto-launch after a respring or reboot); before, iOS suspended it with no link and Wi-Fi dropped.
- HA's `screensaver_timeout` setting (settings topic) sets the screensaver; 0 turns it off.

### Kiosk tweak 1.2
- Home button works normally (iOS Settings reachable); returns to the dashboard after 2 min idle on the home screen. Wake still skips the lock screen; banners still suppressed.
- `mqttdash-kiosk wake` / `sleep` (Darwin notifications) wake or lock the screen remotely.
- Lock / unlock clicks and the charging chime are muted while the panel is locked; timestamped `/tmp/kiosk_debug.log`.
- After a respring or reboot it unlocks before starting the dashboard, so the app starts in the foreground.

### Home Assistant Integration
- Setup asks nothing; panels register themselves on their first hello. A panel without a layout shows a "no layout yet" note instead of borrowing another panel's layout.
- Options reduced to the dashboard editor (with optional sidebar entry) and battery care. Removed: entity mirroring list (the entities your layouts use are always mirrored), entity reference, add device manually, profile JSON editing.
- Actions reduced to `reload` and `set_device_profile` (now with a device picker). Removed `push_config`, `reload_config`, `set_device_settings`, `publish_snapshot`, `prune_unassigned`, `dump_state`, `republish_reload_all`, `dump_store`, `dump_runtime_cfg` and `dump_device_config`; use **Download diagnostics** instead (secrets redacted).
- Notify entity per panel (`notify.send_message`) replaces the `notify.mqttdash_<id>` and `ha_mqtt_dash.notify` actions.
- Entity names translated and in sentence case; Brightness is 5–100 %; new Screensaver number. Keep awake, brightness, screensaver and orientation live only in HA (a profile's `device` block is ignored), and the settings topic always carries all of them.
- Requires Home Assistant 2026.5 or newer.
- **Dashboard editor inside HA:** admin-only panel at `/mqttdash-editor` without HA toolbar (full content area), sidebar entry optional (options → Open the dashboard editor); linked from the integration options and each panel's device page. Uses HA's login over admin-only WebSocket commands (`ha_mqtt_dash/devices`, `get_profile`, `apply_profile`). Loads the panel's current layout in its orientation, follows the HA theme, fits the window (icon rail and drawer on smaller screens).
- **Wake screen** and **Check battery** buttons per panel; a panel that's unreachable over MQTT is woken with its charger plug.
- **Battery care:** switches the charger plug between a start/stop level (default 35–80 %). Readings come over MQTT; only an unanswering panel is woken by power (quietly, rate limited) and locked again afterwards, with the plug restored. Fail-safe charging when a wake goes unanswered or after 4 h without a report. Optional presence: works only while someone is home. Configure in options → Battery care; switch, level numbers and a status sensor per panel.
- **Last contact** diagnostic sensor per panel: when it last sent anything, its link state and the last charger wake.
- Media player commands for volume, mute, output (`select_source`), shuffle and repeat, validated and limited to allowlisted entities.
- Album art / print thumbnails → `mqttdash/art/<entity_id>`; camera frames → `mqttdash/camera/<entity_id>/frame` on demand.
- New widget fields passed through (`camera_entity`, `refresh_interval`, printer target/layer/preview entities, appliance `progress_entity`/`phase_entity` with WashData auto-detection, `temp_step`, timer `presets`, `show_art`).
- Attributes published as JSON / ISO 8601 instead of Python reprs.
- Security: commands only for entities that are controllable widgets; no device purge over MQTT; push API admin-only and no longer re-opened on restart.
- Fixes: a registered panel whose hardware GUID was left on the purged list (from deleting an older device on the same iPad) had every hello ignored; device renames reverting after restart (in-place option mutation), pushed profiles pruned before their device onboards, leftover retained attributes, snapshot floods on reconnect, startup-blocking tasks, duplicate HTTP routes.

### Dashboard editor
- Runs inside HA: panel picker, load current layout, deploy over HA's connection, HA-themed and window-fitting UI. `tools/build_editor.sh` bundles it into the integration. Previews match the new cards.
- **Add cards from entities:** search Home Assistant entities by name and drag one onto the screen; the card type follows the domain (light, climate, media player…). Card types are grouped; Value and Button are folded into Sensor and Scene (old profiles still load).
- Entity fields pick from HA by friendly name, filtered to what the card accepts. The Entities tab (local entity list, bulk add, sync) is gone.
- Toolbar: Material Design icons, panel picker + Load, orientation, undo/redo, Deploy with an unsaved-changes dot; Profile JSON, Help and Clear layout in the ⋮ menu. The iPad model picker is gone: the canvas follows the panel's own screen.
- Card settings: name, entity and card options first; Appearance shows only what that card uses; position in a collapsed section; no internal ID field. Grid and navigation bar when nothing is selected; pixel sizes under "Cell size and spacing".
- Removed: the 6-step tutorial (now a one-page Help and an empty-page hint), the standalone mode (share links, separate toolbar), the "HA mirror entities" list, the banner text and the panel settings (keep awake, screensaver, clock size), which belong to the panel's HA entities.
- `Delete` removes the selected card, `Esc` deselects. Fixed: loading a profile dropped its navigation-bar colors; drops onto a page with its own grid used the shared grid.

### Experimental: video on panels
- **Video media player** per panel (`media_player.<panel>_video`): `play_media` with a YouTube link or a video URL. HA resolves it with yt-dlp and relays the H.264 HLS the iPad 1 decodes in hardware (≤ 480p, with audio) from its own HTTP server (port 8765), byte for byte, without transcoding. Pause, play, seek and stop; the panel reports state and position.
- **Video card** (editor, Media group): plays the panel's video at the card's size and keeps playing on other pages; without one, videos open full screen.
- **Cast from the YouTube app** with `tools/cast_bridge` (a YouTube TV receiver run on any LAN machine). See [docs/video.md](docs/video.md).

### Styling fixes
- Timers show their accent color when idle too, as in the editor.
- Editor previews use the entities' live states (on/off, brightness, sensor values, climate mode) and the app's color rules, so a card looks the same in the editor as on the panel.

### Repository and tooling
- One public repo: the integration, the dashboard editor (`editor/`) and the iPad packages (`releases/`). The iOS app source stays private. The standalone GitHub Pages editor is gone; the editor lives in Home Assistant.
- `install_ipad.sh`: one command installs the app on a jailbroken iPad over SSH - detects the iOS version, picks the legacy (armv7) or modern (arm64) build, handles the legacy SSH algorithms iOS 5 needs, optional kiosk tweak.
- `tools/deploy_to_ha.sh` (dev): dry-run by default, backup, editor rebuild, verified sync, restart and wait for the entry to load. Fixed: the old deploy silently skipped every `__init__.py` on the HA Samba share (it vetoes `._*` names, which rsync uses for temp files); it now syncs `--inplace` and verifies the copy.
- `tools/release_check.sh` + CI (hassfest, HACS, pytest, ruff, editor lint/build/bundle freshness, tag-driven draft releases), ported from ha_creality_ws / ha_washdata.
- Removed the standalone-only REST endpoints (`/api/ha_mqtt_dash/apply_profile`, `/entities`) and the "API access" options step; the in-HA editor uses admin-only WebSocket commands.

---

## 0.5.1 - 2026-06-10

A feature + reliability release: a new **cover** widget (blinds / shades / garage doors, with tilt), a fix for the iOS MQTT client failing to connect to strict brokers, a data-freshness watchdog that recovers from a stuck backend, and a reworked dev/deploy workflow.

### iOS App

#### New widget type

**`cover`** – Blinds, shades, RF shades, and garage doors (`cover.*` entities)
- Controls **adapt to the entity's `supported_features`** by default: open/close are always shown; the stop button appears only when the cover supports it; a position slider appears for covers that report position; tilt buttons and a tilt slider appear when tilt is supported
- **Granular, orderable controls** (`cover_items`): choose exactly which controls appear — `open`, `close`, `stop`, `position`, `presets`, `tilt_open`, `tilt_close`, `tilt_slider` — and their order (top→bottom in tall tiles, row sequence in wide tiles). The older coarse `cover_controls` (`buttons`/`slider`/`presets`/`tilt`) is still accepted and auto-expanded
- **Elastic layout**: `cover_layout` (`auto` / `horizontal` / `vertical`) sets orientation. In vertical layout the position/tilt sliders render as **upright sliders** (full-height travel) beside a button column, so they stay usable in tall 1×N tiles
- Tilt controls use **drawn slat icons** that take the button text color (render correctly on iOS 5.1, where the previous glyphs showed as empty squares, and stay visible on light tiles); the status readout is height-capped so controls aren't cramped
- **Position-preset buttons** (`position_presets`, default `0 / 25 / 75 / 100`) for one-tap positioning
- Center label shows state (`OPEN` / `CLOSED` / `OPENING` / `CLOSING`) plus the current position percentage when available
- `protected: true` requires a confirmation tap before open/close (recommended for garage doors); the stop button is never gated
- Publishes `open_cover` / `close_cover` / `stop_cover` / `set_cover_position` and the tilt equivalents

#### MQTT connection reliability — fixed
- Fixed a bug where the CONNECT packet could be silently truncated if the output stream was not yet writable the instant it opened, leaving strict brokers (e.g. mosquitto 2.x) waiting forever with no CONNACK (`connect timeout`). Outbound writes are now buffered and flushed as the socket accepts data
- Added an **MQTT 3.1 fallback** option (Settings) for brokers/listeners pinned to the legacy protocol
- Added **Verbose MQTT log** (Settings): logs the CONNECT summary (protocol, client-id, keepalive, credentials present, length) + a hex preview, byte counts, and a clearer timeout diagnostic
- Keepalive is now configurable and the client-id is guaranteed non-empty/unique

#### Data-freshness watchdog
- The app now tracks a backend heartbeat (and all inbound traffic) and forces a reconnect if data goes stale for ~90 s, recovering from a frozen-but-connected backend. Dormant unless the backend actually publishes heartbeats, so older integrations are unaffected

### Home Assistant Integration

#### Cover support
- Routes cover commands to the matching `cover.*` services (`open_cover`, `close_cover`, `stop_cover`, `set_cover_position`, and tilt variants)
- Auto-injects `attr_base` for cover widgets; `current_position`, `current_tilt_position`, and `supported_features` are mirrored automatically

#### Freshness heartbeat
- Publishes a retained per-device heartbeat to `mqttdash/dev/<device_id>/heartbeat` (`{"ts":<unix>,"seq":<n>}`) every ~30 s

### Profile Editor
- Added the **Cover** widget type: live canvas visualization (elastic, matching the iOS layout) plus a config panel to pick **individual controls and reorder them** (↑/↓), choose layout direction, edit position presets, and toggle `protected`

### MQTT topics
- New retained topic `mqttdash/dev/<device_id>/heartbeat` (HA → iPad), payload `{"ts":<unix>,"seq":<n>}`
- Cover commands flow over `mqttdash/cmd/cover.<object>`; cover state/attributes mirror under `mqttdash/statestream/cover/<object>/…` (including `current_position`, `current_tilt_position`, `supported_features`)

---

## 0.5.0 - 2026-04-07

This is a major feature release. Version 0.5.0 brings a brand-new visual profile editor, six new widget types, multi-page dashboard support, a redesigned HA integration with per-device entities, OAuth2-based deploy, and a wave of polish across the iOS app.

---

### Profile Editor — New

A fully featured web-based dashboard designer is now live at:
**https://3dg1luk43.github.io/ha_mqtt_dash_profile_editor/**

Built in React 19 with Vite, dnd-kit drag-and-drop, and Zustand state management. No installation required — open it in any browser and start building.

**Canvas & Layout**
- iPad frame preview with 8 device model presets (iPad 1st gen through iPad Air, plus custom resolution)
- Portrait / landscape toggle
- Drag-and-drop widget placement with resize handles
- Grid overlay with configurable columns, cell dimensions, and margins
- Per-page grid override
- Dev overlay mode (shows grid indices for debugging)

**Configuration**
- Right-sidebar config panel with per-widget-type forms for all 19 widget types
- Common fields: label, entity ID, position, size, format (colors, alignment, font size)
- Widget-specific fields: see individual widget sections below
- Entity ID autocomplete sourced from your live HA instance (requires connection)

**Multi-page support**
- Add, rename, and delete pages via tab bar
- Drag widgets within and across pages
- Per-page grid overrides

**Navbar customization**
- Edge placement: top / bottom / left / right
- Custom background color, active/inactive button colors, text color, border color
- Toggle battery indicator and Keep-Awake button visibility

**Device settings panel**
- Keep-Awake toggle
- Screensaver timeout (seconds; 0 = disabled)
- Screensaver clock font size
- Device orientation (auto / portrait / landscape)

**Profile management**
- Undo / redo (full history stack; Ctrl+Z / Ctrl+Y)
- Auto-save to browser localStorage
- Import: JSON paste or file upload
- Export: clipboard copy or file download
- Share via URL: profile encoded as base64 in the URL fragment

**Home Assistant integration (one-click deploy)**
- OAuth2 connection to your HA instance
- Device ID selector
- ⚡ Deploy button sends the profile directly to the device over MQTT via the integration API
- Entity autocomplete for all widget entity fields
- Token auto-refresh (60 s before expiry)

---

### iOS App

#### New widget types

**`timer`** – Local countdown timer (no entity or MQTT required)
- Configurable default duration (`default_seconds`; default 300 s)
- Tap the time display to start/pause; long-press to reset
- +/− buttons with accelerating repeat (0.4 s → 0.15 s → 0.07 s intervals)
- When finished: 5 red flashes + vibration + system alert sound
- Timer state persists across page switches
- `configurable: false` hides the +/− buttons for a repeat-only mode

**`webpage`** – Embedded web view
- Renders any local URL (dashboards, recipe pages, status pages, etc.)
- Uses WKWebView on iOS 8+ with fallback to UIWebView on iOS 7−
- URL set via `stream_url`

**`mealie`** – Mealie recipe integration
- Connects to a self-hosted Mealie instance
- `recipe_slug: null` opens an interactive recipe picker
- `recipe_slug: "..."` displays a specific recipe directly
- Shows ingredients, steps, or both (`visible_section`)
- Handles URL-safe base64 recipe images

**`sousvide`** – Sous vide cooker status
- Displays on/off state, current temperature, target temperature, and time remaining
- Dims the tile automatically when idle/off

**`appliance`** – Generic appliance status
- Displays running state, current program name, and time remaining
- Dims when off

**`mediaplayer`** – Media player controls
- Shows track title and artist
- Play/pause and next/previous buttons
- Seekable progress bar with position/duration display
- Auto-injects MQTT topics from the entity ID

#### Multi-page support
- Profiles can now contain a `pages` array alongside (or instead of) the flat `widgets` array
- Each page has an optional name and per-page grid override
- Navigation bar with named page tabs; swipe left/right to switch pages
- All pages are pre-rendered; live MQTT state updates apply to all pages simultaneously
- Fully backward compatible: profiles with only a `widgets` array continue to work

#### Climate widget — fixed
- Mode-color tinting was silently broken on iOS 7+ due to a deprecated UIKit API (`UITextAttributeTextColor`)
- Fixed by switching to `NSForegroundColorAttributeName` via a new `_applySegmentTextColor:toSegmentedControl:` helper
- State-based colors (per `state_formats`) are now applied immediately if the entity state is already cached
- Tile background also tints to a darker shade of the active mode color for better readability

#### Weather widget
- Added full multi-attribute display (`attrs` list: temperature, humidity, wind_speed, etc.)
- `attr_units` mapping allows per-attribute unit overrides
- Integration auto-injects `attr_base` topic

#### Notifications
- App now handles push notifications from the HA integration
- Notifications show title + message overlaid on the dashboard
- Screensaver is dismissed on notification arrival

#### Screensaver
- Configurable idle timeout (`screensaverTimeout`, seconds; 0 = disabled)
- Configurable clock font size (`screensaverFontSize`, points)
- Touch anywhere to dismiss; also dismissed by incoming notifications or timer alarms

#### Navbar
- Battery level indicator (optional; shown by default)
- Keep-Awake toggle button (optional; shown by default)
- Custom styling: background, active/inactive/text/border colors
- Placement: top / bottom / left / right (`navbarEdge`)

#### MQTT / connectivity
- Refactored MQTTManager: removed legacy session implementations; now uses a single clean code path
- Battery level now reported via dedicated telemetry topic (replaces heartbeat approach)
- On reconnect, app requests a fresh state snapshot to eliminate stale tiles
- Offboarding: clean removal workflow when a device is deregistered in HA

---

### Home Assistant Integration

#### Per-device HA entities

Each registered device now automatically creates the following entities:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.{device_id}_battery` | Sensor | Battery level (%) from device telemetry |
| `switch.{device_id}_keep_awake` | Switch | Prevent device from sleeping |
| `number.{device_id}_brightness` | Number | Screen brightness (0.0–1.0) |
| `select.{device_id}_orientation` | Select | auto / portrait / landscape |
| `number.{device_id}_screensaver_timeout` | Number | Idle timeout in seconds (0 = off) |
| `number.{device_id}_screensaver_font_size` | Number | Screensaver clock font size (pt) |
| `button.{device_id}_reload_config` | Button | Force profile reload on device |

All entities are backed by HA persistent storage and published to the device via MQTT on change.

#### Per-device notify services

Each device gets its own notify service: `notify.mqttdash_{device_id}`

Use it in automations:
```yaml
service: notify.mqttdash_my_ipad
data:
  title: "Alert"
  message: "Laundry done"
```

#### Profile push API

New HTTP endpoint used by the profile editor's Deploy button:

- `POST /api/ha_mqtt_dash/apply_profile` — receives profile JSON, validates it, stores it, and publishes to the device
- `GET /api/ha_mqtt_dash/entities` — returns entity list for editor autocomplete
- Security: local-network only (RFC-1918 + loopback), Bearer token required, rate-limited (20 req / 60 s per IP), 512 KB body limit

#### Profile validation
- Maximum 20 pages, 200 widgets per page, 500 widgets total
- String values capped at 4096 characters
- JSON round-trip sanitization

#### New services

| Service | Description |
|---------|-------------|
| `ha_mqtt_dash.set_device_profile` | Push a profile to a device programmatically |
| `ha_mqtt_dash.dump_store` | Debug: dump HA Store contents to log |
| `ha_mqtt_dash.dump_runtime_cfg` | Debug: dump runtime config to log |
| `ha_mqtt_dash.dump_device_config` | Debug: dump per-device config to log |

#### Persistent storage

Profiles and device settings are now stored in HA's persistent storage (`.storage/ha_mqtt_dash`). They survive HA restarts and are restored without requiring the device to reconnect.

#### Device registry

Devices now appear in HA's device registry with meaningful names. All per-device entities are grouped under the device entry.

---

## 0.4.6 - 2026-03-15

- Initial device registry support
- Version bump and release binary updates

## 0.4.5 - 2026-03-10

- Weather attribute support (`attrs`, `attr_units`)
- Unified release script (`release.sh`) with variant selection
- Build system cleanup (legacy / modern / universal targets)

## [0.4.4] and earlier

See git history.
