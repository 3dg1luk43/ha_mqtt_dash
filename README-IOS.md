# iPad MQTT Dashboard Deployment Guide

This guide explains how to install the prebuilt iPad dashboard application and the companion Home Assistant integration. No local compilation is required; you will deploy the signed `.deb` to your jailbroken iPad and install the integration via HACS.

## 1. Home Assistant preparation

### Install the integration through HACS
1. Open HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/3dg1luk43/ha_mqtt_dash` as type **Integration**.
3. Select **iPad MQTT Dashboard** from HACS and install.
4. Restart Home Assistant once the files are copied.

### Create a dedicated MQTT user in the broker add-on
Create the dashboard credentials directly in your MQTT broker add-on (e.g., Mosquitto) and restart the add-on so the broker loads the new user/password.
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

3. Add or update the broker ACL so the dashboard account is restricted to the `mqttdash/#` topic tree (consult the add-on docs for `acl` or `aclfile` instructions).
4. Save the add-on configuration and click **Restart** to apply the changes.

These broker credentials are what you will enter in the iPad app Settings to connect to the broker.

### Configure MQTT access
- Ensure an MQTT broker (e.g., Mosquitto add-on) is running and reachable on your LAN.
- Create the dashboard login in the broker add-on (see previous section) and restart the add-on.
- Restrict the created account to `mqttdash/#` via ACLs so the dashboard user cannot access unrelated topics.

## 2. Install and configure the integration
1. After the restart, go to Settings → Devices & Services → **Add Integration** → search for “MQTT Dashboard”.
2. Follow the prompts to onboard the first device and optionally bootstrap a starter profile.
3. The integration publishes retained configs to `mqttdash/config/<device_id>/config` and mirrors entity state to `mqttdash/statestream/...`.

## 3. Installing the prebuilt iPad app (.deb)

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
3. Enter the MQTT broker host, port (default 1883), the dedicated MQTT username/password, and the `device_id` defined in Home Assistant.
4. Save and connect. The app will fetch its retained config and render the assigned profile.

## 5. Managing profiles and devices
- Edit profiles through the integration options (HACS → Integrations → MQTT Dashboard → Configure → “Edit device profile”).
- After saving, the integration sends a transient `reload` request and republishes retained config automatically.
- Maintenance services: `ha_mqtt_dash.push_config`, `ha_mqtt_dash.set_device_settings`, `ha_mqtt_dash.publish_snapshot`. Rename is handled by the app’s hello/prev_id and backend migration; deletion uses Home Assistant’s Delete Device.

## 6. Logging and troubleshooting
- iPad: Long-press → View Logs to inspect connection messages.
- Home Assistant: Check Settings → System → Logs for messages tagged with `ha_mqtt_dash`.
- MQTT: `mosquitto_sub -v -t 'mqttdash/#'` verifies topic flow.

## 7. Frequently asked questions

**Do I need to compile the app?** No. Install the provided `.deb` either via a repository or directly with `dpkg -i` on the device.

**Why do I need a dedicated MQTT user?** It isolates the dashboard's access to the broker and lets you restrict permissions (read/write) to only the `mqttdash/#` hierarchy. Restart the broker add-on after creating the user so credentials and ACLs are loaded.

**Can I use TLS or WebSockets?** Not yet. The app speaks MQTT 3.1.1 over plain TCP, so keep the broker on a trusted network segment.

**How do I keep the screen awake?** Toggle the Keep Awake switch entity that the integration creates for each device. The value is retained and applied on reconnect.

**What happens if the device is deleted in Home Assistant?** The integration publishes an offboarding signal `{ "action": "offboard" }` to the device’s settings/request topics. The iOS app stops MQTT, clears the stored Device ID (keeping the internal GUID), shows an “offboarded” banner, and opens Settings so you can enter a new Device ID. This prevents deleted devices from auto-recreating themselves.

## 8. Change log (app highlights)
- 0.1.2: Keep-awake enforcement honours retained settings; sensor text layout remains stable during live updates; integration manifest/loggers updated.
- 0.1.3: Offboard action support — app clears Device ID and returns to onboarding if the backend purges or deletes the device.

Refer to `ha_mqtt_dash/README.md` for low-level integration behaviour and service descriptions.
