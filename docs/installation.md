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

**Option A — installer script (recommended):**

```bash
./install_ipad.sh root@<ipad-ip>            # detects iOS and installs the matching build
./install_ipad.sh root@<ipad-ip> --kiosk    # + kiosk tweak (iOS 5.x)
```

It needs OpenSSH on the iPad (Cydia). Default SSH password on most jailbreaks is `alpine` - change it. Manual install also works: copy the matching `.deb` from `releases/` and run `dpkg -i` on the iPad.

**Option B — via Cydia/Sileo repository:** host the `.deb` and generated `Packages` index on any web server and add the source URL on the iPad.

## First launch

1. Long-press anywhere on the screen to open the menu and tap **Settings**.
2. Enter the MQTT broker host, port (default `1883`), the dedicated MQTT username/password, and the `device_id` you added in HA.
3. Save. The app subscribes to `mqttdash/config/<device_id>/config`, loads the retained config, and renders the dashboard.

Settings also exposes connection options for awkward brokers: **MQTT 3.1 fallback**
(use legacy MQTT 3.1 instead of 3.1.1) and **Verbose MQTT log** (detailed wire-level
diagnostics in View Logs). Leave both off unless a connection won't establish — see
[Troubleshooting](troubleshooting.md).

## Profile editor

The integration ships the editor as an admin-only panel at **`/mqttdash-editor`**. It's deliberately *not* in the sidebar. Open it from **Settings → Devices & services → iPad MQTT Dashboard → Configure → Open the dashboard editor**, or from a panel's device page (**Visit**). It uses your HA login: pick the panel in the toolbar, **⤓ Load** its current layout, edit, then **⚡ Deploy**. It follows your HA theme.

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
| `button.<device_id>_wake_screen` | Button | Turn the screen on, even while the panel is asleep |
| `button.<device_id>_check_battery` | Button | Ask for a fresh battery reading without waking the screen |
| `binary_sensor.<device_id>_online` | Binary sensor | Reachable; attribute `screen` is `awake` / `asleep` |
| `switch.<device_id>_battery_care` | Switch | Enable charger control (see below) |
| `number.<device_id>_charge_start_level` / `_charge_stop_level` | Number | Charge window (%) |
| `sensor.<device_id>_battery_care_status` | Sensor | `charging` / `resting` / `disabled` / `no_charger` …, with the reason |

All values are two-way: change the entity in HA and the device receives the update over MQTT immediately. Values are retained and re-applied on reconnect.

### Sleeping panels and battery care

While the screen is off, iOS suspends the app. With **Reachable asleep** on (app Settings, default on) the app keeps a tiny background MQTT link (iOS VoIP mode) that only listens for *wake* and *report* requests and reports the battery about every 10 minutes, so HA can wake the screen or read the battery without the panel staying awake.

**Battery care** stops an old iPad from sitting at 100 % on the charger. Put the charger on a smart plug, then open the integration options → **Battery care** and pick the plug, the start level (default 35 %) and the stop level (default 80 %). HA switches the plug on at/below the start level and off at/above the stop level, asks for a reading every 5 min while charging (15 min otherwise), and turns the plug **on** as a fail-safe if the panel stops reporting for 45 min.

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
