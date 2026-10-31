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
3. Go to Settings → Devices & services → **Add integration** → "iPad MQTT Dashboard". Setup asks nothing.

Panels add themselves: when the app connects with a panel name (see [First launch](#first-launch)), the panel shows up as a device with its entities ([Per-panel entities](#per-panel-entities)). Until you deploy a layout from the editor it shows a short "no layout yet" note.

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
2. Enter the MQTT broker host, port (default `1883`), the dedicated MQTT username/password, and a panel name (`device_id`, for example `kitchen`: letters, digits, `-` and `_`).
3. Save. The panel registers in Home Assistant, then loads its layout from `mqttdash/config/<device_id>/config`.

Settings also exposes connection options for awkward brokers: **MQTT 3.1 fallback**
(use legacy MQTT 3.1 instead of 3.1.1) and **Verbose MQTT log** (detailed wire-level
diagnostics in View Logs). Leave both off unless a connection won't establish — see
[Troubleshooting](troubleshooting.md).

## Profile editor

The integration ships the editor as an admin-only panel at **`/mqttdash-editor`**. It isn't in the sidebar by default (switch that on under options → **Open the dashboard editor**). Open it from **Settings → Devices & services → iPad MQTT Dashboard → Configure → Open the dashboard editor**, or from a panel's device page (**Visit**). It uses your HA login and theme: pick the panel in the toolbar, **Load** its current layout (or start empty), edit, then **Deploy**. Help in the ⋮ menu lists the gestures and shortcuts.

## Per-panel entities

Each panel is a device in Home Assistant with these entities:

| Entity | Type | What it does |
|--------|------|--------------|
| Battery | Sensor | Battery level (%) |
| Charging | Binary sensor | The iPad reports it's charging |
| Online | Binary sensor | Reachable over MQTT; attribute `screen` is `awake` / `asleep` |
| Last contact | Sensor (diagnostic) | When the panel itself last sent anything; attributes: link state, last battery report, last charger wake and its result |
| Keep awake | Switch | Keep the screen on |
| Brightness | Number | Screen brightness, 5–100 % |
| Screensaver | Number (config) | Seconds without a touch before the clock screensaver shows; 0 = off |
| Orientation | Select | `auto` / `portrait` / `landscape` |
| Reload | Button | Send the layout again and reload it on the panel |
| Wake screen | Button | Turn the screen on: over MQTT, or with the charger plug when the panel is unreachable |
| Check battery | Button (diagnostic) | Fresh battery reading: over MQTT (screen stays off), else a quiet charger wake |
| Battery care | Switch (config) | Charger control on/off (see below) |
| Charge start level / Charge stop level | Number (config) | Charge window (%) |
| Battery care status | Sensor (diagnostic) | `charging` / `resting` / `checking` / `away` / `disabled` / `no_charger` …, with the reason |
| *(panel name)* | Notify | `notify.send_message` shows a popup on the panel |

Keep awake, brightness, screensaver and orientation live only in Home Assistant (not in the layout): changes reach the panel at once and are re-applied when it reconnects.

### Sleeping panels and battery care

While the screen is off, iOS suspends the app. With **Reachable asleep** on (app Settings, default on) the app keeps a tiny background MQTT link (iOS VoIP mode) that only listens for *wake* and *report* requests and reports the battery about every 10 minutes, so HA can wake the screen or read the battery without the panel staying awake.

**Battery care** stops an old iPad from sitting at 100 % on the charger. Put the charger on a smart plug, then open the integration options → **Battery care** and pick the plug, the start level (default 35 %) and the stop level (default 80 %). HA switches the plug on at/below the start level and off at/above the stop level.

A reading is wanted every 5 min while charging (15 min otherwise). A reachable panel (`online`, or `sleeping` over the background link) is asked over MQTT and the screen stays off. Only a panel that doesn't answer is woken by power: HA switches the charger on (or off and on), which lights the iPad's screen; the app reports and is told to lock again (it ignores that while someone is using it, keep-awake is on or a timer runs), and the plug goes back to how it was. With the kiosk tweak installed the lock clicks and the charging chime are muted while the panel is locked. Charger wakes happen at most every 30 min while charging and every 2 h otherwise. A panel that doesn't answer a charger wake, or hasn't reported for 4 h, keeps the charger **on** as a fail-safe.

Use a charger that can power an iPad: the iPad 1 needs a 10 W (2 A) adapter; a weaker USB port charges it slowly, or not at all while the screen is on. If the plug is on but the iPad reports not charging (it may show "Charging is not supported with this accessory"), HA turns the plug off for a minute and on again, at most hourly; after three tries that don't help, the status sensor warns to check the cable or the adapter.

Optionally pick people (or device trackers): battery care then only works while one of them is home. Otherwise it pauses (status `away`): no checks, no wakes, the plug is left as it is.

## Notifications

Each panel has a notify entity, so the standard action works:

```yaml
action: notify.send_message
target:
  entity_id: notify.kitchen
data:
  title: Laundry
  message: Washing machine done
```

The older `notify.mqttdash_<device_id>` and `ha_mqtt_dash.notify` actions are gone.

## Panels: rename, remove

- **Layout:** design it in the editor and press Deploy (or use `ha_mqtt_dash.set_device_profile` in an automation).
- **Rename:** change the panel name in the app's Settings. The app sends a stable hardware ID with every hello, so Home Assistant moves the device, its layout and settings to the new name and clears the old retained topics.
- **Remove:** delete the device in Home Assistant. Its retained topics are cleared and the app returns to its welcome screen.

## Actions

| Action | What it does |
|--------|--------------|
| `ha_mqtt_dash.reload` | Publish every panel's layout again and make the panels reload it |
| `ha_mqtt_dash.set_device_profile` | Replace a panel's layout (profile JSON as exported from the editor) and reload it |

For debugging use **Download diagnostics** on the integration or on a panel's device page: panels, layouts, the config each panel receives, telemetry and battery care, with secrets removed.
