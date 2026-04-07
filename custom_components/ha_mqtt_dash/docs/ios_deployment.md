# iPad MQTT Dashboard Deployment Guide

This guide shows how to install the prebuilt iPad app and companion Home Assistant integration. You deploy the signed `.deb` to your jailbroken iPad and add the integration via HACS.

## 1. Home Assistant preparation

### Install the integration through HACS
1. Open HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/3dg1luk43/ha_mqtt_dash` as type **Integration**.
3. Select **iPad MQTT Dashboard** from HACS and install.
4. Restart Home Assistant once the files are copied.

### Create a dedicated MQTT user in the broker add-on
Create dashboard credentials in your MQTT broker add‑on (e.g., Mosquitto) and restart the add‑on so the broker reloads them.
1. Open Settings → Add-ons → select your MQTT broker add-on (Mosquitto Broker).
2. Open the **Configuration** tab and add a login entry for the dashboard, for example:

```json
{
   "logins": [
      { "username": "mqttdash", "password": "<strong-password>" }
   ],
   "anonymous": false
}
```

3. Add or update the broker ACL so the dashboard account is restricted to the `mqttdash/#` topic tree (consult the add‑on docs for `acl` or `aclfile`).
4. Save the add-on configuration and click **Restart** to apply the changes.

These broker credentials are what you will enter in the iPad app Settings to connect to the broker.

### Configure MQTT access
- Ensure a 3.1.1 TCP listener is enabled and reachable on your LAN.
- Create the dashboard login in the broker add‑on (see previous section) and restart the add‑on.
- Restrict this account to `mqttdash/#` via ACLs.

## 2. Install and configure the integration
1. After the restart, go to Settings → Devices & Services → **Add Integration** → search for “MQTT Dashboard”.
2. Follow the prompt to enter the first device_id. A starter per‑device profile is created.
3. The integration publishes retained configs to `mqttdash/config/<device_id>/config` and mirrors entity state to `mqttdash/statestream/...`.

## 3. Install the prebuilt iPad app (.deb)

### Option A: Add a Cydia/Sileo repository
1. Host the `.deb` and metadata on a web server:
   ```bash
   mkdir -p repo/debs
   cp com.yourorg.mqttdash_0.1.2_iphoneos-arm.deb repo/debs/
   cd repo
   dpkg-scanpackages debs > Packages
   gzip -c Packages > Packages.gz
   cat <<'EOF' > Release
   Origin: MQTT Dash
   Label: MQTT Dash
   Suite: stable
   Version: 1.0
   Codename: ios
   Architectures: iphoneos-arm
   Components: main
   Description: MQTT Dash app repository
   EOF
   ```
2. Upload `repo/` to an HTTPS host (e.g., `https://example.com/cydia`).
3. On the iPad, open Cydia/Sileo → Sources → Edit → Add → enter the repository URL.
4. Install **MQTT Dash** from the new repository.

### Option B: Manual installation via SSH
```bash
scp com.yourorg.mqttdash_0.1.2_iphoneos-arm.deb root@ipad.local:/var/root/
ssh root@ipad.local "dpkg -i /var/root/com.yourorg.mqttdash_0.1.2_iphoneos-arm.deb"
```
Replace `ipad.local` with the device hostname or IP. After installation, respring if prompted.

## 4. First launch configuration
1. Start **MQTT Dash** on the iPad.
2. Long-press the screen to open the menu and tap **Settings**.
3. Enter the MQTT broker host, port (1883), the dedicated MQTT username/password, and the `device_id` you added in Home Assistant.
4. Save and connect. The app will fetch its retained config and render the assigned profile.

## 5. Manage profiles and devices
- Edit a device’s profile in the integration Options (“Edit device profile”). Profiles are per device.
- After saving, the integration sends a transient `reload` and republishes retained config.
- Useful services: `ha_mqtt_dash.push_config`, `ha_mqtt_dash.reload_config`, `ha_mqtt_dash.set_device_settings`, `ha_mqtt_dash.publish_snapshot`, `ha_mqtt_dash.set_device_profile`, `ha_mqtt_dash.dump_device_config`.
- Rename: the app sends `guid`/`prev_id` in hello; the backend migrates to the new device_id and cleans old retained topics.
- Delete device in HA to purge retained topics and offboard the device (the app clears its stored Device ID and returns to welcome).

## 6. Logging and troubleshooting
- iPad: Long-press → View Logs to inspect connection messages.
- Home Assistant: Check Settings → System → Logs for messages tagged with `ha_mqtt_dash`.
- MQTT: `mosquitto_sub -v -t 'mqttdash/#'` verifies topic flow.

## 7. Frequently asked questions

**Do I need to compile the app?** No. Install the provided `.deb` either via a repository or directly with `dpkg -i` on the device.

**Why do I need a dedicated MQTT user?** It isolates the dashboard's access to the broker and lets you restrict permissions (read/write) to only the `mqttdash/#` hierarchy. Restart the broker add-on after creating the user so credentials and ACLs are loaded.

**Can I use TLS or WebSockets?** No. Old iOS versions do not support latest WebSockets nor latest TLS ciphers. The app speaks MQTT 3.1.1 over plain TCP; keep the broker on a trusted network segment and restrict the account.

**How do I keep the screen awake?** Toggle the Keep Awake switch entity that the integration creates for each device. The value is retained and applied on reconnect.

**What happens if the device is deleted in Home Assistant?** The integration clears retained topics and publishes `{ "action": "offboard" }` transiently to `.../request` and retained to `.../settings`. The app stops MQTT, clears the stored Device ID (keeps its internal GUID), shows an offboarded banner, and opens Settings.

## 8. Change log (app highlights)
- 0.1.2: Keep-awake enforcement honours retained settings; sensor text layout remains stable during live updates; integration manifest/loggers updated.
- 0.1.3: Offboard action support — app clears Device ID and returns to onboarding if the backend purges or deletes the device.

Refer to the main README for integration details and services.
