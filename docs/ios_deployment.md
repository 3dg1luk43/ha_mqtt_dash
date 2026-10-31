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

1. Go to Settings → Devices & services → **Add integration** → "iPad MQTT Dashboard". Setup asks nothing.
2. Panels register themselves when the app connects with a panel name (next section) and appear as devices with their entities.

## 2. Install the iPad app

### Choosing the right package

| Package variant | Architecture | iOS version |
|----------------|-------------|-------------|
| Universal | armv7 + arm64 | 5.1+ / 12.0+ |
| Legacy | armv7 | 5.1 — 10.3.x (iPad 1, 2, mini 1) |
| Modern | arm64 | 12.0+ (iPad Air+) |

Download from the `releases/` folder in this repository.

### Option A — Installer script (recommended)

```bash
./install_ipad.sh root@<ipad-ip>            # detects iOS and installs the matching build
./install_ipad.sh root@<ipad-ip> --kiosk    # + kiosk tweak (iOS 5.x)
```

It needs OpenSSH on the iPad (Cydia). Default SSH password on most jailbreaks is `alpine` - change it. Manual install also works: copy the matching `.deb` from `releases/` and run `dpkg -i` on the iPad.

### Option B — Cydia/Sileo repository

Host the `.deb` and a generated `Packages` index on any web server, then add the source URL on the iPad via Cydia/Sileo → Sources → Edit → Add.

## 3. First launch

1. Start **MQTT Dash** on the iPad.
2. Long-press the screen to open the menu and tap **Settings**.
3. Enter: broker host, port (default `1883`), MQTT username/password, and a panel name (`device_id`, for example `kitchen`).
4. Save and connect. The panel registers in Home Assistant and shows its layout (a "no layout yet" note until you deploy one).

## 4. Design a dashboard

In Home Assistant open **Settings → Devices & services → iPad MQTT Dashboard → Configure → Open the dashboard editor** (or the device page → **Visit**). The editor opens inside Home Assistant (admin only; a sidebar entry can be switched on there):

- Pick the panel in the toolbar; **Load** brings in its current layout.
- Search for an entity on the left and drag it onto the screen: the card type follows the entity. Or pick a card type from the list.
- Click a card to change it on the right; click empty space for the grid and navigation bar. Pages are the tabs in the screen's navigation bar.
- **Deploy** sends the layout and the panel redraws within seconds. A dot on Deploy means unsaved changes.

It uses your Home Assistant login; nothing leaves your network.

## 5. Per-panel entities

Each panel is a device in Home Assistant with battery, charging, online, last contact, keep awake, brightness, screensaver, orientation, reload, wake screen, check battery, battery care and a notify entity. The full list is in [Installation](installation.md#per-panel-entities).

## 6. Managing panels

**Layout:** design it in the dashboard editor and press Deploy.

**Rename:** change the panel name in the app's Settings. The app sends its stable hardware ID with every hello; Home Assistant moves the device, layout and settings and clears the old retained topics.

**Remove:** delete the device in Home Assistant. Retained topics are cleared and the app returns to its welcome screen.

## 7. Actions

`ha_mqtt_dash.reload` and `ha_mqtt_dash.set_device_profile` (notifications: `notify.send_message` on the panel's notify entity); see [Installation](installation.md#actions). For debugging use **Download diagnostics** on the panel's device page.

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

```bash
./install_ipad.sh root@<ipad-ip> --kiosk
```

The installer adds the tweak next to the app and resprings; MQTTDash then launches automatically. The home button works normally (iOS Settings stays reachable) and the dashboard returns after 2 minutes idle on the home screen. `ssh root@<ipad-ip> mqttdash-kiosk wake` wakes the screen remotely, `mqttdash-kiosk sleep` locks it. While the panel is locked the lock clicks and the charging chime are muted, so battery-care checks stay silent.

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
Turn on the panel's **Keep awake** switch in Home Assistant. It is re-applied every time the panel reconnects.

**What does the screensaver do?**
After the configured idle timeout with no touches, the screen dims and shows a large clock. Any touch dismisses it. The screensaver is also dismissed automatically when a notification arrives or a local timer finishes.

**What happens when I delete a device in HA?**
The integration sends `{ "action": "offboard" }` to the device, clears all retained topics, and marks the device as purged. The app clears its stored Device ID and returns to the welcome screen. The device's internal GUID is preserved so it can be re-admitted by tapping Onboard if needed.
