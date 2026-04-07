# Troubleshooting

## Connectivity and broker setup

- **MQTT version:** the app requires a **3.1.1 TCP listener**. MQTT v5-only and WebSockets-only listeners will not work.
- **TLS:** not supported by the legacy iOS client (required for iPad 1/iOS 5.1 compatibility). Keep the broker LAN-only.
- **Keepalive / backoff:** keepalive 30 s; connect timeout 12 s; exponential backoff with jitter on reconnect.

## Common CONNACK error codes

| Code | Meaning | Fix |
|------|---------|-----|
| 0 | Connection accepted | — |
| 1 | Unacceptable protocol version | Switch to a 3.1.1 listener |
| 2 | Identifier rejected | Check client ID uniqueness |
| 3 | Server unavailable | Broker down or listener blocked |
| 4 | Bad username/password | Check credentials in Settings |
| 5 | Not authorized | Check ACLs — account needs read/write on `mqttdash/#` |

## App menu and logs

- **Open menu:** long-press anywhere outside a widget. Options: View Logs, Toggle Dev Overlay, Settings.
- **View Logs:** shows recent MQTT events, connection state changes, and profile load messages. Useful first step for any connectivity issue.
- **Toggle Dev Overlay:** draws a faint grid with x,y column/row indices. Helpful when authoring profiles.

## Config not loading

1. Confirm the device_id in the app Settings matches what was added in HA.
2. Check HA logs for `ha_mqtt_dash` — look for errors on startup or on profile publish.
3. Run `ha_mqtt_dash.push_config` from HA Developer Tools → Services to force republish all retained configs.
4. Use `mosquitto_sub -v -t 'mqttdash/#'` on any LAN host to verify the config topic is being published.

## Stale or wrong widget state after reconnect

The app requests a full state snapshot on reconnect. If tiles still show stale data, call `ha_mqtt_dash.publish_snapshot` manually to republish all mirrored entity states.

## Per-device entities not appearing

Entities are created when the integration first processes a device hello. Make sure the app has connected at least once after the integration was installed. If entities are still missing, restart HA and reconnect the device.

## Screensaver

- The screensaver activates after the idle timeout with no touches. Default is disabled (0 seconds).
- Configure timeout via the `number.<device_id>_screensaver_timeout` entity in HA, or via the `device.screensaverTimeout` field in the profile JSON.
- Any touch dismisses it. Notifications from HA and local timer completions also dismiss it.
- If the screensaver font size looks wrong, adjust `number.<device_id>_screensaver_font_size` (points; 0 = device default).

## Screen not staying awake

Toggle the `switch.<device_id>_keep_awake` entity in HA. The setting is retained and re-applied on every reconnect. Alternatively use `ha_mqtt_dash.set_device_settings` with `{ "keep_awake": true }`.

## Climate widget colors not showing

This was a known bug in versions before 0.5.0 — the mode segment control used a deprecated UIKit API (`UITextAttributeTextColor`) that iOS 7+ silently ignores. Update to the 0.5.0 app package. After updating, `state_formats` colors in the profile will work correctly.

## Camera widget showing blank / not refreshing

- Confirm `stream_url` is reachable from the iPad (open it in Safari on the device).
- The ↺ refresh button in the top-right corner reloads the stream on demand.
- If the stream drops frequently, this is usually a network or camera firmware issue rather than an app issue.

## Timer widget not persisting across page switches

Timer state is stored by widget `id`. If the widget has no `id` set, one is auto-generated each time and state is lost on page switch. Add an explicit `id` to the widget definition.

## Profile editor: Deploy button not working

- HA must be reachable at an **HTTPS** URL from your browser. HTTP-only instances are not supported for OAuth2. Use **Export → Copy JSON** and paste into integration options instead.
- The API access window auto-closes after 10 minutes of inactivity. Re-enable it in Integration Options → API Access if the Deploy button reports an auth error.
- The deploy endpoint is local-network only. If your browser is outside the LAN (e.g., behind a VPN that routes traffic externally), requests will be rejected.

## Profile editor: Entity autocomplete not working

Autocomplete is fetched from `GET /api/ha_mqtt_dash/entities`. Confirm the API Access option is enabled in the integration and that your HA OAuth2 connection in the editor is active (check the header — it should show "Connected").

## Notifications not appearing

- Confirm the per-device notify service name: `notify.mqttdash_<device_id>` with hyphens replaced by underscores.
- Check the HA logs for the notify call.
- Verify with `mosquitto_sub -t 'mqttdash/dev/<device_id>/notify'` that the payload is being published.
- The notification topic is non-retained — the app must be connected when it is published.

## Integration setup checklist

1. Broker has a TCP 3.1.1 listener on your LAN.
2. Dashboard MQTT account is restricted to `mqttdash/#`.
3. Integration is installed via HACS and restarted.
4. `device_id` in the app Settings exactly matches what was entered in the integration.
5. App has connected at least once so the integration can process the hello and create entities.

## Add / rename / remove a device

- **Add:** enter a new device_id in HA Options. On the iPad app, set the same device_id in Settings and reconnect.
- **Rename:** change the device_id in HA Options. The app sends its stable GUID in each hello; the integration migrates the record automatically.
- **Remove:** delete the device in HA. The integration purges retained topics and offboards the app. To re-admit, the app sends `{ "action": "onboard" }` via the request topic.

## Useful debug services

| Service | What it logs |
|---------|-------------|
| `ha_mqtt_dash.dump_store` | Full HA Store contents (profiles, settings, purged list) |
| `ha_mqtt_dash.dump_runtime_cfg` | Merged runtime config for all devices |
| `ha_mqtt_dash.dump_device_config` | Resolved config for a single device (what gets published) |
