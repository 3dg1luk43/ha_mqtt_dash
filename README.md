![Installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Installations&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.ha_mqtt_dash.total)
![Latest](https://img.shields.io/github/v/release/3dg1luk43/ha_mqtt_dash)

# Home Assistant MQTT Dashboard

A Home Assistant custom integration and companion iPad app that turns jailbroken iPads into wall-mounted dashboards. Supports everything from iPad 1 on iOS 5.1 through modern iPad Air running iOS 12+. Everything runs over plain MQTT on your LAN — no cloud, no TLS, no app store required.

- **App:** Objective-C (UIKit) — iOS 5.1 through iOS 12+
- **Transport:** MQTT 3.1.1 over plain TCP (no TLS, no WebSockets — required for legacy hardware)
- **Design:** Retained per-device config + retained mirrored entity states; stateless JSON commands per widget
- **Namespace:** fixed `mqttdash/*` for configs, device topics, commands, and mirrored state

## Quick start

1. Install the integration via HACS and add it (setup asks nothing).
2. Create a dedicated MQTT user in your broker add-on and restrict it to `mqttdash/#`.
3. Install the iPad app: `./install_ipad.sh root@<ipad-ip>` (add `--kiosk` for the kiosk tweak). Enter the broker and a panel name in the app's Settings; the panel then appears in Home Assistant.
4. In Home Assistant open **Settings → Devices & services → iPad MQTT Dashboard → Configure → Open the dashboard editor**, design your dashboard and press **Deploy**.

Detailed steps: [Installation guide](docs/installation.md) · [iOS deployment guide](docs/ios_deployment.md)

## Dashboard editor

The drag-and-drop editor is built into the integration and opens inside Home Assistant (admin only, sidebar entry optional): integration options → **Open the dashboard editor**, or a panel's device page → **Visit**. Pick the panel and **Load** its current layout, or start empty: search for an entity and drag it onto the screen, and the matching card is added. Press **Deploy** to send the layout. It uses your Home Assistant login and theme; nothing leaves your network.

## Prebuilt app packages

Signed `.deb` packages are published under `releases/` (and attached to each GitHub release). The installer picks the right one for you:

```bash
git clone https://github.com/3dg1luk43/ha_mqtt_dash && cd ha_mqtt_dash
./install_ipad.sh root@192.168.1.50            # detects iOS, installs, resprings
./install_ipad.sh root@192.168.1.50 --kiosk    # + kiosk tweak (iOS 5.x)
./install_ipad.sh root@192.168.1.50 --dry-run  # only show what it would do
```

It needs OpenSSH on the iPad (Cydia) and works with the legacy SSH algorithms of iOS 5.

| Variant | Architecture | iOS minimum |
|---------|-------------|-------------|
| Universal | armv7 + arm64 | 5.1 / 12.0 |
| Legacy | armv7 | 5.1 (iPad 1, 2, mini 1) |
| Modern | arm64 | 12.0 (iPad Air+) |

## Kiosk mode (optional)

An optional **MQTTDash Kiosk** MobileSubstrate tweak keeps the iPad on the dashboard: auto-launch on boot, wake skips the lock screen and returns to the app, the dashboard comes back after 2 minutes idle on the home screen, and banners are suppressed. The home button works normally, so iOS Settings stays reachable. Designed for iOS 5.1.x wall-panel installs. See [iOS deployment guide](docs/ios_deployment.md#8-optional-kiosk-mode) for details.

## Widget types (20)

`light` · `switch` · `scene` · `button` · `sensor` · `value` · `person` · `label` · `clock` · `weather` · `climate` · `camera` · `printer` · `timer` · `webpage` · `mealie` · `sousvide` · `appliance` · `mediaplayer` · `cover`

Full schema reference: [Profiles and widgets](docs/profiles_and_widgets.md)

## Documentation

- [Supported devices](docs/supported_devices.md)
- [Installation](docs/installation.md)
- [Profiles and widgets](docs/profiles_and_widgets.md)
- [MQTT topics](docs/mqtt_topics.md)
- [iOS deployment guide](docs/ios_deployment.md)
- [Troubleshooting](docs/troubleshooting.md)
- [How to report issues](docs/issue_reporting.md)

## Integration highlights

- **Panels register themselves** — setup asks nothing; a panel appears as a device when the app first connects.
- **Per-panel entities** — battery, charging, online, last contact, keep awake, brightness, screensaver, orientation, reload, wake screen, check battery and battery care. Panel settings live only in HA and reach the panel at once.
- **Notifications** — a notify entity per panel (`notify.send_message`).
- **State mirroring** — the entities your layouts use are mirrored to retained MQTT topics automatically. No separate MQTT Statestream setup.
- **Diagnostics** — Download diagnostics shows what each panel receives, with secrets removed.
- **Multi-page support** — profiles can contain a `pages` array; all pages receive live MQTT updates simultaneously.
- **Built-in editor** — design layouts in Home Assistant (admin-only panel, optional sidebar entry) and deploy them to a panel in one click.
- **Wake and battery care** — wake a sleeping panel from HA, read its battery without waking it, and keep an old iPad's battery between two levels with a smart plug (optionally only while someone is home).

## Onboarding flow

1. App connects, sends hello (with optional `prev_id`/`guid`), subscribes to `mqttdash/config/<id>/config`.
2. Integration creates or updates the device record, creates HA entities, and publishes retained config.
3. Device renders the grid; retained settings (brightness, orientation, keep-awake, screensaver) apply immediately.

## Notes and caveats

- Layouts are per panel, keyed by the panel name (`device_id`).
- The integration mirrors states itself — do not enable or depend on the HA Statestream integration.
- TLS and WebSockets are not supported by the legacy iOS client. Keep the broker LAN-only and use a restricted MQTT account.

## How to report issues

See [docs/issue_reporting.md](docs/issue_reporting.md) for the capture checklist and issue template.
