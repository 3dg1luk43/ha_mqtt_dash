# Installation

This page covers both parts: the Home Assistant integration and the iPad app.

Packages
- Universal: armv7 + arm64
- Legacy: armv7 only (iPad 1 and other 32‑bit models)
- Modern: arm64 only (iOS 12+)

Prereqs (MQTT broker)
1. Ensure your MQTT broker (e.g., Mosquitto add‑on) exposes a TCP 3.1.1 listener (no TLS/WebSockets required).
2. Create a dedicated dashboard user and restart the add‑on to apply:
	 - Mosquitto add‑on example (simplified snippet):
		 {
			 "logins": [ { "username": "mqttdash", "password": "<strong-password>" } ],
			 "anonymous": false
		 }
	 - Restrict this user to the `mqttdash/#` namespace via ACLs in your broker. Consult your broker’s docs for ACL configuration.

Home Assistant integration (HACS)
1. In HACS → Integrations → ⋮ → Custom repositories, add this repo as type Integration.
2. Install “iPad MQTT Dashboard” and Restart Home Assistant.
3. Go to Settings → Devices & Services → Add Integration → search “iPad MQTT Dashboard”. Enter the first device_id when prompted. A starter per‑device profile will be created.
4. Open the integration Options to edit that device’s profile JSON (widgets and layout) and pick entities to mirror. Profiles are per device (keyed by device_id).

iPad app (.deb)
Option A — via repo: host `.deb` on a simple Cydia/Sileo repo and add the source on the iPad.
Option B — manual via SSH (password should be 'alpine'):
	scp {package}.deb root@{ipad ip}:/var/root/
	ssh root@{ipad ip} "dpkg -i /var/root/{package}.deb"

First launch (onboarding)
1. Long‑press anywhere outside widget → Settings.
2. Enter broker host, port 1883, the dedicated MQTT username/password, and the device_id you added in HA.
3. Save. The app subscribes to `mqttdash/config/<device_id>/config`, loads the retained config, and renders the UI.

Mirroring and updates
- The integration mirrors selected entities to retained topics under `mqttdash/statestream/...` (built‑in; you do not need HA’s Statestream integration).
- On HA startup or when you manually call the “Publish snapshot” service, a full retained snapshot is sent. Live changes publish deltas.
- When you save a profile, the device receives a transient `reload`, then a fresh retained config is published.

Per‑device settings
- Control brightness (0..1), keep_awake, and orientation (auto|portrait|landscape) via the service `ha_mqtt_dash.set_device_settings`. Values are retained and re‑applied on reconnect.