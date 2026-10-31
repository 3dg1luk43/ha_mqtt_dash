# Troubleshooting

## Connectivity and broker setup

- **MQTT version:** the app speaks **MQTT 3.1.1** over TCP by default. MQTT v5-only and WebSockets-only listeners will not work. A **MQTT 3.1 fallback** toggle in Settings switches to the legacy 3.1 protocol for brokers/listeners pinned to it.
- **TLS:** not supported by the legacy iOS client (required for iPad 1/iOS 5.1 compatibility). Keep the broker LAN-only.
- **Keepalive / backoff:** keepalive defaults to 30 s (configurable in Settings); connect timeout 12 s; exponential backoff with jitter on reconnect.

## App stuck on "connecting" / `connect timeout` (no CONNACK)

If the log reaches `sending CONNECT` but never `rx bytes`, the broker is receiving nothing usable from the app. Things to try:

1. **Update the app** — builds from 0.5.1 on fixed a bug where the CONNECT packet could be truncated before it reached the broker (strict brokers such as mosquitto 2.x then waited forever with no CONNACK).
2. **Enable Settings → Verbose MQTT log** — it logs the CONNECT summary (protocol, client-id, keepalive, whether credentials are present, length) plus a hex preview and byte counts, and a clearer timeout diagnostic.
3. **Try Settings → MQTT 3.1 fallback** if your listener is pinned to MQTT 3.1.
4. **Check the broker logs** with `log_type all` and `connection_messages true` — confirm it receives the CONNECT and, if it rejects it, why.
5. Confirm the dashboard account has read/write on `mqttdash/#` (see CONNACK code 5 below).

## Dashboard stops updating but stays "connected"

The app runs a data-freshness watchdog: it watches the integration's retained heartbeat (`mqttdash/dev/<device_id>/heartbeat`, ~30 s) plus all other inbound traffic, and forces a reconnect if data goes stale (~90 s). If tiles freeze and never recover, confirm the integration is publishing the heartbeat (`mosquitto_sub -v -t 'mqttdash/dev/+/heartbeat'`); a pre-0.5.1 integration won't publish one, so the watchdog stays dormant.

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

1. The panel name in the app's Settings is the device in Home Assistant; a panel without a deployed layout shows a "no layout yet" note.
2. Check HA logs for `ha_mqtt_dash`.
3. Press the panel's **Reload** button, or run `ha_mqtt_dash.reload`, to send every layout again.
4. **Download diagnostics** on the panel's device page shows the exact config the panel receives.
5. `mosquitto_sub -v -t 'mqttdash/config/#'` on any LAN host shows what is published.

## Stale or wrong widget state after reconnect

The app requests a full state snapshot on reconnect. If tiles still show stale data, press the panel's **Reload** button.

## Per-device entities not appearing

A panel appears in Home Assistant when the app first connects (its hello). Make sure the app has connected at least once with the right broker and a panel name. A panel you deleted in Home Assistant stays ignored until the app re-onboards (Settings → save).

## Screensaver

- The screensaver activates after the idle timeout with no touches. Default is disabled (0 seconds).
- Set the timeout with the panel's **Screensaver** number in Home Assistant (seconds, 0 = off).
- Any touch dismisses it. Notifications from HA and local timer completions also dismiss it.

## Screen not staying awake

Turn on the panel's **Keep awake** switch in Home Assistant. It is re-applied every time the panel reconnects.

## Climate widget colors not showing

This was a known bug in versions before 0.5.0 — the mode segment control used a deprecated UIKit API (`UITextAttributeTextColor`) that iOS 7+ silently ignores. Update to the 0.5.0 app package. After updating, `state_formats` colors in the profile will work correctly.

## Camera widget showing blank / not refreshing

- Confirm `stream_url` is reachable from the iPad (open it in Safari on the device).
- The ↺ refresh button in the top-right corner reloads the stream on demand.
- If the stream drops frequently, this is usually a network or camera firmware issue rather than an app issue.

## Timer widget not persisting across page switches

Timer state is stored by widget `id`. If the widget has no `id` set, one is auto-generated each time and state is lost on page switch. Add an explicit `id` to the widget definition.

## Dashboard editor: not opening or Deploy fails

- The editor is admin only. Open it from integration options → **Open the dashboard editor**, or browse to `/mqttdash-editor`.
- "No panels" in the toolbar: the iPad has not registered yet. Open the app once with the right broker and device ID.
- A Deploy error message shows in the toolbar (hover for the full text). Check **Settings → System → Logs** for `ha_mqtt_dash`.
- After updating the integration, reload the browser tab so the new editor files load.

## Notifications not appearing

- Send to the panel's notify entity (`notify.send_message` with `entity_id: notify.<panel>`) The older `notify.mqttdash_<device_id>` and `ha_mqtt_dash.notify` actions no longer exist.
- Check the HA logs for the notify call.
- Verify with `mosquitto_sub -t 'mqttdash/dev/<device_id>/notify'` that the payload is being published.
- The notification topic is non-retained — the app must be connected when it is published.

## Integration setup checklist

1. Broker has a TCP 3.1.1 listener on your LAN.
2. Dashboard MQTT account is restricted to `mqttdash/#`.
3. Integration is installed via HACS and added (setup asks nothing).
4. The app has a panel name in Settings and has connected at least once, so the panel registered.

## Add / rename / remove a device

- **Add:** set a panel name in the app's Settings and connect; the panel registers itself.
- **Rename:** change the panel name in the app's Settings. The app sends its stable hardware ID in each hello, so Home Assistant moves the device, layout and settings automatically.
- **Remove:** delete the device in Home Assistant. Retained topics are cleared and the app is offboarded. To re-admit it, save the app's Settings again (it sends `{ "action": "onboard" }`).

## Debugging

Use **Download diagnostics** on the integration or on a panel's device page (Settings → Devices & services). It contains the panels, their layouts, the config each panel receives, settings, telemetry, battery care and last contact, with API keys, passwords, tokens and URL credentials removed.
