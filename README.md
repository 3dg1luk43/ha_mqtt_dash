# Home Assistant MQTT Dashboard

This repository contains the Home Assistant custom integration that powers the iPad MQTT Dashboard.

- App: Objective‑C (UIKit, iOS 5 APIs) for legacy iPads
- Transport: MQTT 3.1.1 over TCP (no TLS/WebSockets)
- Design: Retained per‑device config + retained mirrored states; stateless JSON commands per widget
- Namespace: fixed `mqttdash/*` for configs, device topics, commands, and mirrored state

Quick start:
1) Create a dedicated MQTT user (broker add‑on) and keep it LAN‑only. 2) Install the integration via HACS and add it; you’ll enter the first device_id and get a starter profile. 3) Install the iPad app (.deb) and enter broker + device_id; the UI renders from the retained config.

## Start here
- [Supported devices](docs/supported_devices.md)
- [Installation](docs/installation.md)
- [Profiles and widgets](docs/profiles_and_widgets.md)
- [MQTT topics](docs/mqtt_topics.md)
- [Troubleshooting](docs/troubleshooting.md)
- [iOS deployment guide](docs/ios_deployment.md)
- [How to report issues](docs/issue_reporting.md)

Integration highlights
- Publishes a retained config for each device_id; profiles are stored per device (no shared profile library).
- Mirrors selected entities to retained statestream topics under `mqttdash/statestream/...` (built‑in; no separate Statestream integration needed).
- Device presence: retained LWT at `mqttdash/dev/<device_id>/status` (online/offline).
- On save, devices receive a transient `reload` then a fresh retained config.

Onboarding flow (concise)
1. App connects, sends hello (and prev_id/guid), subscribes to `mqttdash/config/<id>/config`.
2. Integration creates/updates the device record and publishes retained config; if purged earlier, the app can send `{"action":"onboard"}` to re‑admit.
3. Device renders grid; retained settings (brightness/orientation/keep_awake) apply if present.

Notes and caveats
- Profiles are per device and keyed by device_id. Sharing profiles across devices is not supported in the current UI flow.
- The integration mirrors states itself; do not enable or depend on the HA Statestream integration.
- TLS/WebSockets are not supported by the legacy iOS client; keep the broker LAN‑only and use a restricted account.

How to report issues
See `docs/issue_reporting.md` for the capture checklist and template.
