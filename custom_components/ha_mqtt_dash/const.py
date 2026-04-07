DOMAIN = "ha_mqtt_dash"

CONF_DEVICES = "devices"
CONF_PROFILES = "profiles"

CONF_MIRROR_ENTITIES = "mirror_entities"  # list[str]
CONF_MIRROR_AUTO = "mirror_auto"  # bool — derive mirror list from profile entity refs
CONF_PLACEHOLDER_ON_REMOVE = "placeholder_on_remove"  # bool
CONF_API_ENABLED = "api_enabled"  # bool — allow profile editor HTTP push endpoint

# hass.data key storing the Unix timestamp until which the push API is active
CONF_API_UNTIL_KEY = f"{DOMAIN}_api_until"

# Dispatcher signal names
SIGNAL_DEVICE_SETTINGS_UPDATED = f"{DOMAIN}_device_settings_updated"

# Fixed mqttdash namespace (replaces legacy 'ha/*' topics). User configuration of bases removed.
FIXED_CONFIG_BASE = "mqttdash/config"
FIXED_DEVICE_BASE = "mqttdash/dev"
FIXED_COMMAND_BASE = "mqttdash/cmd"
FIXED_STATESTREAM_BASE = "mqttdash/statestream"

# Persistent storage (HA Store)
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.store"