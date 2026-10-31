DOMAIN = "ha_mqtt_dash"

CONF_DEVICES = "devices"
CONF_PROFILES = "profiles"

CONF_PLACEHOLDER_ON_REMOVE = "placeholder_on_remove"  # bool
CONF_EDITOR_SIDEBAR = "editor_sidebar"  # bool — show the dashboard editor in the sidebar


# Dispatcher signal names
SIGNAL_DEVICE_SETTINGS_UPDATED = f"{DOMAIN}_device_settings_updated"
SIGNAL_LAST_CONTACT = f"{DOMAIN}_last_contact"

# Fixed mqttdash namespace (replaces legacy 'ha/*' topics). User configuration of bases removed.
FIXED_CONFIG_BASE = "mqttdash/config"
FIXED_DEVICE_BASE = "mqttdash/dev"
FIXED_COMMAND_BASE = "mqttdash/cmd"
FIXED_STATESTREAM_BASE = "mqttdash/statestream"

# Persistent storage (HA Store)
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.store"