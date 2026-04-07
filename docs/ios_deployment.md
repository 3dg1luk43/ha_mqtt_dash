# iPad MQTT Dashboard — Deployment Guide

This guide covers installing the prebuilt iPad app and the companion HA integration from scratch.

## 1. Home Assistant preparation

### Install the integration via HACS

1. Open HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/3dg1luk43/ha_mqtt_dash` as type **Integration**.
3. Select **iPad MQTT Dashboard** from HACS and install.
4. Restart Home Assistant.

### Create a dedicated MQTT user

1. Open Settings → Add-ons → select your MQTT broker (e.g., Mosquitto Broker).
2. Open the **Configuration** tab and add a login entry:

```json
{
  "logins": [
    { "username": "mqttdash", "password": "<strong-password>" }
  ],
  "anonymous": false
}
```

3. Add an ACL restricting this account to the `mqttdash/#` topic namespace (consult the add-on docs for ACL syntax).
4. Click **Restart** to apply.

### Add the integration

1. Go to Settings → Devices & Services → **Add Integration** → search "iPad MQTT Dashboard".
2. Enter the first `device_id` (e.g., `kitchen-ipad`). A starter profile is created automatically.
3. The integration publishes a retained config to `mqttdash/config/<device_id>/config` and creates per-device HA entities.

## 2. Install the iPad app

### Choosing the right package

| Package variant | Architecture | iOS version |
|----------------|-------------|-------------|
| Universal | armv7 + arm64 | 5.1+ / 12.0+ |
| Legacy | armv7 | 5.1 — 10.3.x (iPad 1, 2, mini 1) |
| Modern | arm64 | 12.0+ (iPad Air+) |

Download from the `releases/` folder in this repository.

### Option A — Install via SSH

```bash
scp com.3dg1luk43.mqttdash_0.5.0-1+legacy_iphoneos-arm.deb root@<ipad-ip>:/var/root/
ssh root@<ipad-ip> "dpkg -i /var/root/com.3dg1luk43.mqttdash_0.5.0-1+legacy_iphoneos-arm.deb"
```

Default SSH password on most jailbreaks is `alpine`. Respring the device after install if prompted.

### Option B — Cydia/Sileo repository

Host the `.deb` and a generated `Packages` index on any web server, then add the source URL on the iPad via Cydia/Sileo → Sources → Edit → Add.

## 3. First launch

1. Start **MQTT Dash** on the iPad.
2. Long-press the screen to open the menu and tap **Settings**.
3. Enter: broker host, port (default `1883`), MQTT username/password, and the `device_id` added in HA.
4. Save and connect. The app subscribes to its config topic, loads the retained profile, and renders the dashboard.

## 4. Design a dashboard with the profile editor

Open the visual editor in any browser:

**https://3dg1luk43.github.io/ha_mqtt_dash_profile_editor/**

- Drag widget types from the left palette onto the iPad canvas.
- Configure widgets in the right-hand config panel.
- Add pages, rename them, and set per-page grid overrides via the tab bar.
- Design is auto-saved to browser localStorage. Export to JSON at any point.

**Deploy directly to the device (requires HA at an HTTPS URL):**

1. Click **⚡ Deploy** in the editor header.
2. Enter your HA URL (e.g., `https://homeassistant.local:8123`) and click **Connect**.
3. Approve the OAuth2 request in HA. You'll be redirected back to the editor.
4. Enter the **Device ID** and click **▶ Send Profile**. The dashboard reloads within seconds.

Subsequent deploys: click ⚡ Deploy again — it redeploys to the same device in one click.

**If your HA is HTTP-only:** use **Export → Copy JSON** and paste the JSON into Integration Options → Edit device profile.

**Security:** the editor stores everything in browser localStorage only. No data is sent to any external server. The OAuth2 API session auto-closes after 10 minutes of inactivity. The deploy endpoint accepts connections from local-network addresses only.

## 5. Per-device HA entities

Each device automatically gets these entities, grouped under the device in the HA device registry:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.<device_id>_battery` | Sensor | Battery % from device telemetry |
| `switch.<device_id>_keep_awake` | Switch | Prevent device from sleeping |
| `number.<device_id>_brightness` | Number | Screen brightness (0.0–1.0) |
| `select.<device_id>_orientation` | Select | `auto` / `portrait` / `landscape` |
| `number.<device_id>_screensaver_timeout` | Number | Idle timeout in seconds (0 = off) |
| `number.<device_id>_screensaver_font_size` | Number | Screensaver clock font size (pt) |
| `button.<device_id>_reload_config` | Button | Force profile reload on device |

All are two-way: changing a HA entity pushes the update to the device over MQTT immediately. Values are retained and re-applied on reconnect.

Each device also gets a notify service for use in automations:

```yaml
service: notify.mqttdash_kitchen_ipad
data:
  title: "Laundry"
  message: "Washing machine done"
```

## 6. Managing devices

**Edit profile:** Integration Options → Edit device profile (JSON), or use the profile editor + Deploy.

**Rename device:** Change the `device_id` in HA Options. The app sends its stable GUID in each hello; the integration migrates the device record and purges old retained topics automatically.

**Remove device:** Delete the device in HA. The integration purges all retained topics and sends an offboard command. The app clears its stored Device ID and returns to the welcome screen.

## 7. Useful services

| Service | Description |
|---------|-------------|
| `ha_mqtt_dash.push_config` | Republish retained configs for all devices |
| `ha_mqtt_dash.reload_config` | Trigger reload then republish all configs |
| `ha_mqtt_dash.set_device_settings` | Push settings to a specific device (retained) |
| `ha_mqtt_dash.publish_snapshot` | Publish full state snapshot for all mirrored entities |
| `ha_mqtt_dash.set_device_profile` | Overwrite a device's profile and republish |
| `ha_mqtt_dash.dump_device_config` | Log a device's resolved config for debugging |

## 8. Optional: Kiosk mode

The **MQTTDash Kiosk** package is an optional MobileSubstrate tweak that locks the iPad into the dashboard permanently. Install it if you want a dedicated wall panel that no one can accidentally navigate away from.

### What it does

- **Auto-launch on boot** — MQTTDash starts automatically 2 seconds after SpringBoard finishes loading. No need to tap the app icon.
- **Home button** — instead of going to the home screen, pressing home dims and locks the screen (identical to the power button). The SpringBoard icon grid is never shown.
- **Power button** — normal sleep behavior. Screen dims and device locks.
- **Screen wake** — pressing either button while sleeping unlocks the screen silently (no lock-screen UI) and brings MQTTDash straight to the foreground.
- **Notification Center** — the pull-down notification shade is suppressed entirely.
- **Notification banners** — system banners from other apps are dropped. MQTTDash's own in-app notification overlay still works.
- **Lock screen icon** — hidden from the status bar.

The result: the iPad behaves like a dedicated appliance. Boot → dashboard. Sleep/wake → dashboard. Nothing else is accessible from normal use.

### Requirements

- Jailbroken device with **MobileSubstrate** (Cydia Substrate / Substitute) installed
- The main **MQTTDash** app package installed first
- **iOS 5.1.x** — the tweak hooks SpringBoard internals using selectors verified on iOS 5.1.1. It is not tested on iOS 6+ and is not recommended on modern builds.

### Installation

**Via SSH:**

```bash
scp com.3dg1luk43.mqttdash-kiosk_1.0.0-34_iphoneos-arm.deb root@<ipad-ip>:/var/root/
ssh root@<ipad-ip> "dpkg -i /var/root/com.3dg1luk43.mqttdash-kiosk_1.0.0-34_iphoneos-arm.deb"
```

After install, respring or reboot. MQTTDash will launch automatically.

### Uninstalling

```bash
ssh root@<ipad-ip> "dpkg -r com.3dg1luk43.mqttdash-kiosk && killall SpringBoard"
```

SpringBoard restarts and normal home screen behavior returns immediately.

### Debug log

If the tweak is not behaving as expected, check `/tmp/kiosk_debug.log` on the device for a trace of every hook invocation.

---

## 9. Logging and troubleshooting

- **iPad:** Long-press → **View Logs** to inspect connection messages and MQTT events.
- **Home Assistant:** Settings → System → Logs → filter for `ha_mqtt_dash`.
- **MQTT traffic:** `mosquitto_sub -v -t 'mqttdash/#'` on any LAN host to watch all topic traffic.

See [troubleshooting.md](troubleshooting.md) for common errors and fixes.

## 9. FAQ

**Do I need to compile the app?**
No. Install the prebuilt `.deb` via SSH or Cydia.

**Why a dedicated MQTT user?**
Isolates dashboard access and lets you restrict the account to `mqttdash/#`. The restriction prevents the dashboard from reading or writing unrelated broker topics.

**Can I use TLS or WebSockets?**
No. Old iOS versions (especially iOS 5.1 on iPad 1) do not support modern TLS cipher suites, and the embedded MQTT client uses plain TCP. Keep the broker on a trusted LAN segment.

**How do I keep the screen awake?**
Toggle the `switch.<device_id>_keep_awake` entity in HA, or use `ha_mqtt_dash.set_device_settings`. The setting is retained and re-applied on every reconnect.

**What does the screensaver do?**
After the configured idle timeout with no touches, the screen dims and shows a large clock. Any touch dismisses it. The screensaver is also dismissed automatically when a notification arrives or a local timer finishes.

**What happens when I delete a device in HA?**
The integration sends `{ "action": "offboard" }` to the device, clears all retained topics, and marks the device as purged. The app clears its stored Device ID and returns to the welcome screen. The device's internal GUID is preserved so it can be re-admitted by tapping Onboard if needed.
