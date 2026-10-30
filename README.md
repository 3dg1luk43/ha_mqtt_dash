![Installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Installations&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.ha_mqtt_dash.total)
![Latest](https://img.shields.io/github/v/release/3dg1luk43/ha_mqtt_dash)

# Home Assistant MQTT Dashboard

A Home Assistant custom integration and companion iPad app that turns jailbroken iPads into wall-mounted dashboards. Supports everything from iPad 1 on iOS 5.1 through modern iPad Air running iOS 12+. Everything runs over plain MQTT on your LAN — no cloud, no TLS, no app store required.

- **App:** Objective-C (UIKit) — iOS 5.1 through iOS 12+
- **Transport:** MQTT 3.1.1 over plain TCP (no TLS, no WebSockets — required for legacy hardware)
- **Design:** Retained per-device config + retained mirrored entity states; stateless JSON commands per widget
- **Namespace:** fixed `mqttdash/*` for configs, device topics, commands, and mirrored state

## Quick start

1. Install the integration via HACS, enter your first `device_id`, and get a starter profile.
2. Create a dedicated MQTT user in your broker add-on and restrict it to `mqttdash/#`.
3. Install the iPad app: `./install_ipad.sh root@<ipad-ip>` (add `--kiosk` for the kiosk tweak). Enter broker + `device_id` in the app's Settings.
4. In Home Assistant open **Settings → Devices & services → iPad MQTT Dashboard → Configure → Open the dashboard editor**, design your dashboard and hit **⚡ Deploy**.

Detailed steps: [Installation guide](docs/installation.md) · [iOS deployment guide](docs/ios_deployment.md)

## Dashboard editor

The drag-and-drop editor is built into the integration and opens inside Home Assistant (admin only, not added to the sidebar): integration options → **Open the dashboard editor**, or a panel's device page → **Visit**. Pick the panel, **⤓ Load** its current layout, design on the iPad frame and **⚡ Deploy**. It uses your Home Assistant login and follows your HA theme; nothing leaves your network.

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

- **Per-device HA entities** — each registered device automatically creates battery, brightness, keep-awake, orientation, screensaver timeout, screensaver font size, and reload-config entities. All are two-way: change the entity in HA and the device responds over MQTT.
- **Per-device notify services** — `notify.mqttdash_<device_id>` lets automations push notifications directly to a device.
- **Device registry** — devices appear in the HA device registry with all entities grouped under them.
- **Profile persistence** — profiles are stored in HA persistent storage and survive restarts without requiring the device to reconnect.
- **State mirroring** — the integration mirrors selected entities to retained statestream topics. No separate HA Statestream integration needed.
- **Multi-page support** — profiles can contain a `pages` array; all pages receive live MQTT updates simultaneously.
- **Built-in editor** — design layouts in Home Assistant (admin-only panel, not in the sidebar) and deploy them to a panel in one click.
- **Wake and battery care** — wake a sleeping panel from HA, read its battery without waking it, and keep an old iPad's battery between two levels with a smart plug.

## Onboarding flow

1. App connects, sends hello (with optional `prev_id`/`guid`), subscribes to `mqttdash/config/<id>/config`.
2. Integration creates or updates the device record, creates HA entities, and publishes retained config.
3. Device renders the grid; retained settings (brightness, orientation, keep-awake, screensaver) apply immediately.

## Notes and caveats

- Profiles are per device and keyed by `device_id`. The profile editor handles multi-device workflows.
- The integration mirrors states itself — do not enable or depend on the HA Statestream integration.
- TLS and WebSockets are not supported by the legacy iOS client. Keep the broker LAN-only and use a restricted MQTT account.
- The profile push API is local-network only; it rejects requests from public IP addresses even with a valid token.

## How to report issues

See [docs/issue_reporting.md](docs/issue_reporting.md) for the capture checklist and issue template.
