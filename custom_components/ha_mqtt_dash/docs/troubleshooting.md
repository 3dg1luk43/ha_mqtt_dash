# Troubleshooting

## Connectivity and broker setup
- MQTT version: ensure a 3.1.1 TCP listener (not MQTT v5-only, and not WebSockets-only)
- Keepalive/backoff: keepalive 30s; connect timeout 12s; exponential backoff with jitter

## Common errors (CONNACK)
- 0: Connection accepted
- 1: Unacceptable protocol version — use MQTT 3.1.1 listener
- 2: Identifier rejected — check client ID uniqueness
- 3: Server unavailable — broker down or listener blocked
- 4: Bad username/password — fix credentials in Settings
- 5: Not authorized — adjust broker ACLs for `mqttdash/#`

## UI and behavior tips
- Unexpected publishes are soft-suppressed without recent user touch; dedup within 2 seconds
- Toggle the Dev Overlay via the dashboard menu to see grid indices while authoring

## Notifications (HA → iPad popup)
- Domain service: `ha_mqtt_dash.notify` (fields: `device_id`/`ha_device`, `message`, `title`)
- Per-device: `notify.mqttdash_<device_id>` (hyphens become underscores)
- Behavior: non-retained JSON to `mqttdash/dev/<device_id>/notify`

## Retention policy
- Retained: device configs, device status/hello reflection, device settings, mirrored entity states/attributes
- Non‑retained: device requests (e.g., reload, snapshot) and entity command messages

## Menu and logs access
- Open menu: Long‑press anywhere outside widgets. A menu appears with “View Logs”, “Toggle Dev Overlay”, and “Settings”.
- Toggle dev overlay: Use the “Toggle Dev Overlay” menu item.
- Note: There are no on‑screen menu/logs buttons anymore.

## Integration setup (Home Assistant)
1. Install the `ha_mqtt_dash` custom component via HACS and restart.
2. Ensure the MQTT broker has a 3.1.1 TCP listener.
3. Add the MQTT Dashboard integration and enter the first device_id; a starter per‑device profile will be created.
4. Edit that device’s profile in Options; the integration publishes a retained config for that device.
5. Optional: set per‑device settings (brightness/orientation/keep_awake). These are retained.

## Credentials and prerequisites
- Broker: MQTT 3.1.1 over TCP on your LAN. No TLS/WebSockets required.
- ACLs: Restrict access to the dashboard’s MQTT topics per device according to your broker’s best practices.
- iPad app: Set broker host/port and credentials in Settings on first run.

## Add or remove a device
- Add: In HA Options, add a device (device_id). Power on the iPad app with that device_id; it will fetch retained config and render immediately.
- Rename: Change the name on the device; the app includes a stable GUID/prev_id in hello, and the integration migrates the device_id and purges old retained topics.
- Remove: Use Home Assistant's built‑in Delete Device. The integration purges retained topics, offboards the device, and prevents auto‑recreation. To re‑admit, the app can send `{ "action": "onboard" }` to `mqttdash/dev/<id>/request`.
