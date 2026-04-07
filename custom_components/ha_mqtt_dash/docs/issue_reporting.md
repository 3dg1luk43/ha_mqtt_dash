# How to Report Issues (ha_mqtt_dash + iPad Dashboard)

Thanks for helping improve the project! Include the details below so we can reproduce and fix issues quickly.

Please include the template at the bottom of this page in your issue and fill out every field you can. Screenshots or short screen recordings are very helpful.

## Before you file

- Use the latest released .deb and the latest `ha_mqtt_dash`.
- Confirm your broker exposes an MQTT 3.1.1 TCP listener (not MQTT v5‑only/WebSockets‑only).
- If profile‑specific, try a minimal profile (1–2 widgets).

## Required information

Provide these details up front:

- App package version and variant:
  - .deb name you installed (e.g., com.example.mqttdash_0.4.3-2+legacy_iphoneos-arm.deb) and whether it’s Universal, Legacy (armv7), or Modern (arm64).
- Device details:
  - Model and generation (e.g., iPad 1st gen, iPad mini 2).
  - iOS version shown in Settings (e.g., 5.1.1, 9.3.6, 12.5.7).
  - Device ID used in the app/integration (e.g., ipad1-lr).
- Home Assistant:
  - Core version (Settings → About) and `ha_mqtt_dash` integration version (git commit or release tag).
- MQTT broker:
  - Vendor and version (e.g., Mosquitto 2.0.18, EMQX, HiveMQ).
  - Protocol/listener: TCP 3.1.1 enabled? Any v5-only or WebSockets-only listeners?
  - Auth/ACLs: Are topics `mqttdash/#` allowed for this client?
- Network notes:
  - All on LAN? Any VLAN/firewall/NAT rules? Any MQTT proxy/bridge in between?

## Reproduction steps (critical)

Please list exact, numbered steps to reproduce. Include timing if relevant.

Example:
1) Launch the app, it shows the dashboard grid.
2) Long-press to open menu → Settings → set broker host to 192.168.1.10, port 1883, username `ipad`, password `•••`.
3) Return to dashboard, wait ~5s for retained config to load.
4) Tap the “Living Room” light tile.
Expected: Light turns on; tile shows ON state.
Actual: Tile flashes, but state stays OFF.

## Logs and captures

Attach the following where possible (redact secrets):

1) App logs (on the iPad):
   - Long-press on the dashboard background → “View Logs”.
   - Scroll to the time of the problem and copy the relevant lines.

2) Home Assistant logs:
   - Filter for `ha_mqtt_dash` entries during the reproduction window.

3) MQTT traffic capture (same LAN, optional):
   - Subscribe to the dashboard namespace to collect retained configs and live traffic during repro (optional).
   - Narrow to specific topics when helpful (device topics or a single mirrored entity).

4) Device config snapshot from HA (optional but very helpful):
   - Use the integration’s “dump device config” service and attach the JSON.

5) Minimal profile JSON (if the issue depends on layout/widgets):
   - Include the smallest profile that still reproduces the issue.

## Attachments checklist

- [ ] App logs (text)
- [ ] HA logs filtered for `ha_mqtt_dash` (text)
- [ ] MQTT capture of `mqttdash/#` during repro (text)
- [ ] Device config JSON (from integration dump) (json)
- [ ] Minimal profile snippet (json)
- [ ] Screenshots or screen recording (optional)

Privacy and redaction

- Redact passwords, tokens, and any public IP addresses.
- Keep the device_id in place—this helps correlate logs and topics.
- Broker hostnames inside your LAN are OK to include (e.g., 192.168.1.10).

---

Copy‑paste issue template

Paste the template below into your issue and replace all placeholders:

```markdown
##Title: [Short summary — what went wrong]

###Summary
- What happened: <one or two sentences>
- What you expected: <one or two sentences>

###Environment
- App package: <deb filename + version> (Universal | Legacy armv7 | Modern arm64)
- Device: <model + generation> — iOS <version>
- Device ID: <e.g., ipad1-lr>
- Home Assistant: Core <version>
- ha_mqtt_dash integration: <version/tag/commit>
- MQTT broker: <vendor + version>; 3.1.1 TCP listener: <yes/no>; WebSockets-only: <yes/no>; v5-only: <yes/no>
- Network: <LAN/Wi‑Fi details; any VLAN/firewall/proxy>

###Steps to reproduce
1. <step>
2. <step>
3. <step>

Expected
- <expected behavior>

Actual
- <actual behavior + any visible errors>

###Relevant logs

- App logs (time window):
  <paste>

- Home Assistant logs (filtered for ha_mqtt_dash):
  <paste>


###MQTT capture (during repro)

<paste mosquitto_sub output for topics under mqttdash/#>


###Profile and config
- Minimal profile (if applicable):
  { /* minimal JSON that still reproduces */ }

- Device config JSON (from integration dump):
  { /* redacted if needed */ }


Additional context
- Screenshots / recording: <links or attach>
- Frequency: <always/intermittent>
- First seen in version: <when did it start>
```

---

If anything in the template doesn’t apply, mark it as “N/A” rather than deleting it. This helps us see what was considered.
