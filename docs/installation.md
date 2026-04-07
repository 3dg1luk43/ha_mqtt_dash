# Installation

This page covers both parts: the Home Assistant integration and the iPad app.

## App packages

Three variants are available under `releases/`:

| Variant | Architecture | iOS minimum | Use case |
|---------|-------------|-------------|----------|
| Universal | armv7 + arm64 | 5.1 / 12.0 | Fat binary — covers everything |
| Legacy | armv7 | 5.1 | iPad 1, iPad 2, iPad mini 1st gen |
| Modern | arm64 | 12.0 | iPad Air and later |

## Prerequisites — MQTT broker

1. Ensure your broker (e.g., Mosquitto add-on) exposes a **TCP 3.1.1 listener**. TLS and WebSockets are not supported by the legacy iOS client.
2. Create a dedicated dashboard user and restart the add-on to apply. Mosquitto add-on example:

```json
{
  "logins": [{ "username": "mqttdash", "password": "<strong-password>" }],
  "anonymous": false
}
```

3. Restrict this user to the `mqttdash/#` topic namespace via your broker's ACL configuration.

## Home Assistant integration (HACS)

1. In HACS → Integrations → ⋮ → **Custom repositories**, add `https://github.com/3dg1luk43/ha_mqtt_dash` as type **Integration**.
2. Install **iPad MQTT Dashboard** and restart Home Assistant.
3. Go to Settings → Devices & Services → **Add Integration** → search "iPad MQTT Dashboard".
4. Enter the first `device_id` when prompted. A starter per-device profile is created automatically.

After the integration is set up, each device gets a set of HA entities created automatically — see [Per-device entities](#per-device-entities) below.

## iPad app (.deb)

**Option A — via SSH:**

```bash
scp com.3dg1luk43.mqttdash_0.5.0-1+legacy_iphoneos-arm.deb root@<ipad-ip>:/var/root/
ssh root@<ipad-ip> "dpkg -i /var/root/com.3dg1luk43.mqttdash_0.5.0-1+legacy_iphoneos-arm.deb"
```

Default SSH password on most jailbreaks is `alpine`. Respring if prompted.

**Option B — via Cydia/Sileo repository:** host the `.deb` and generated `Packages` index on any web server and add the source URL on the iPad.

## First launch

1. Long-press anywhere on the screen to open the menu and tap **Settings**.
2. Enter the MQTT broker host, port (default `1883`), the dedicated MQTT username/password, and the `device_id` you added in HA.
3. Save. The app subscribes to `mqttdash/config/<device_id>/config`, loads the retained config, and renders the dashboard.

## Profile editor

The drag-and-drop web editor runs in any browser — nothing to install:

**https://3dg1luk43.github.io/ha_mqtt_dash_profile_editor/**

**Designing a layout:**
- Drag widget types from the palette onto the iPad canvas.
- Configure each widget in the right-hand config panel.
- Switch between pages using the tab bar; add/rename/delete pages as needed.
- Full undo/redo (Ctrl+Z), auto-saves to localStorage.

**Deploying to a device:**

Requires HA reachable at an HTTPS URL from your browser (e.g., `https://homeassistant.local:8123` with a valid cert, or Nabu Casa). For HTTP-only instances use **Export → Copy JSON** and paste into the integration options instead.

1. Click **⚡ Deploy** in the editor header (or **Export → Send to Home Assistant**).
2. Enter your HA URL and click **Connect**. HA's OAuth2 login page opens — approve the request.
3. Enter the **Device ID** and click **▶ Send Profile**. The profile is saved and the device reloads within seconds.
4. On subsequent iterations, ⚡ Deploy in the header redeploys to the same device with one click.

**Security:** everything in the editor is stored in browser localStorage only — no data leaves your machine. The OAuth2 session auto-closes after 10 minutes of inactivity. The deploy endpoint is local-network only and rejects requests from public IP addresses even with a valid token.

## Per-device entities

Each registered device automatically gets the following HA entities:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.<device_id>_battery` | Sensor | Battery level (%) from device telemetry |
| `switch.<device_id>_keep_awake` | Switch | Prevent the device screen from sleeping |
| `number.<device_id>_brightness` | Number | Screen brightness (0.0–1.0) |
| `select.<device_id>_orientation` | Select | `auto` / `portrait` / `landscape` |
| `number.<device_id>_screensaver_timeout` | Number | Idle timeout in seconds (0 = off) |
| `number.<device_id>_screensaver_font_size` | Number | Screensaver clock font size (pt) |
| `button.<device_id>_reload_config` | Button | Force profile reload on the device |

All values are two-way: change the entity in HA and the device receives the update over MQTT immediately. Values are retained and re-applied on reconnect.

## Per-device notify service

Each device also gets a notify service usable in automations:

```yaml
service: notify.mqttdash_kitchen_ipad
data:
  title: "Laundry"
  message: "Washing machine done"
```

Hyphens in `device_id` become underscores in the service name.

## Managing profiles and devices

- **Edit profile:** Integration Options → Edit device profile (JSON paste), or use the profile editor with Deploy.
- **Rename device:** Change the device ID in HA Options. The app sends its stable GUID in each hello; the integration migrates the record and purges old retained topics automatically.
- **Remove device:** Delete the device in HA. The integration purges retained topics and sends an offboard command. The app clears its stored Device ID and returns to the welcome screen.

## Useful services

| Service | Description |
|---------|-------------|
| `ha_mqtt_dash.push_config` | Republish retained configs for all devices |
| `ha_mqtt_dash.reload_config` | Trigger reload then republish configs |
| `ha_mqtt_dash.set_device_settings` | Send settings to a device (retained) |
| `ha_mqtt_dash.publish_snapshot` | Publish full state snapshot for mirrored entities |
| `ha_mqtt_dash.set_device_profile` | Overwrite a device's profile and republish |
| `ha_mqtt_dash.dump_device_config` | Log a single device's resolved config (debug) |
