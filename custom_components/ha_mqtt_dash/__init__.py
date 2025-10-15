from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore
from .const import DOMAIN
import json
from .storage import StorageHelper
import voluptuous as vol  # type: ignore
import homeassistant.helpers.config_validation as cv  # type: ignore
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg  # type: ignore
from homeassistant.helpers import device_registry as dr  # type: ignore

PLATFORMS = ["sensor", "binary_sensor", "switch", "select", "number", "button", "notify"]
from .mqtt_bridge import MqttBridge

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _LOGGER.debug("ha_mqtt_dash: async_setup called")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("ha_mqtt_dash: async_setup_entry starting")
    hass.data.setdefault(DOMAIN, {})
    bridge = MqttBridge(hass, entry)
    # Register update listener BEFORE bridge async_setup so any options writes during
    # storage initialization are observed by the bridge.
    async def _on_update(hass: HomeAssistant, updated: ConfigEntry):
        _LOGGER.debug("ha_mqtt_dash: options updated -> forwarding to bridge")
        await bridge.async_options_updated(updated)
    entry.async_on_unload(entry.add_update_listener(_on_update))

    await bridge.async_setup()
    hass.data[DOMAIN][entry.entry_id] = bridge
    _LOGGER.debug("ha_mqtt_dash: bridge setup complete; registering services")

    # admin/services
    async def _svc_push_config(call):
        _LOGGER.debug("svc:push_config")
        await bridge.async_publish_all_configs()

    async def _svc_reload_config(call):
        _LOGGER.debug("svc:reload_config")
        # Ensure devices reload then receive fresh retained config
        bridge.schedule_republish_reload("svc_reload_config")

    async def _svc_set_device_settings(call):
        _LOGGER.debug(
            "svc:set_device_settings device_id=%s brightness=%s keep_awake=%s orientation=%s",
            call.data.get("device_id"), call.data.get("brightness"), call.data.get("keep_awake"), call.data.get("orientation"),
        )
        await bridge.async_publish_device_settings(
            call.data["device_id"],
            brightness=call.data.get("brightness"),
            keep_awake=call.data.get("keep_awake"),
            orientation=call.data.get("orientation"),
        )

    async def _svc_publish_snapshot(call):
        _LOGGER.debug("svc:publish_snapshot")
        await bridge.async_publish_snapshot()
    async def _svc_prune_unassigned(call):
        _LOGGER.debug("svc:prune_unassigned")
        await bridge.async_prune_unassigned()

    async def _svc_dump_state(call):
        cfg = {**(entry.data or {}), **(entry.options or {})}
        devs = cfg.get("devices", []) or []
        profs = cfg.get("profiles", {}) or {}
        _LOGGER.debug(
            "svc:dump_state devices=%d profiles=%d ids=%s profile_keys=%s",
            len(devs), len(profs), [d.get("device_id") for d in devs if d.get("device_id")], list(profs.keys()),
        )

    async def _svc_republish_reload_all(call):
        _LOGGER.debug("svc:republish_reload_all invoked")
        bridge.schedule_republish_reload("service_call")

    # rename_device and purge_device services removed; use HA built-in Delete Device and profile editing.
    hass.services.async_register(DOMAIN, "push_config", _svc_push_config)
    hass.services.async_register(DOMAIN, "reload_config", _svc_reload_config)
    hass.services.async_register(DOMAIN, "set_device_settings", _svc_set_device_settings)
    hass.services.async_register(DOMAIN, "publish_snapshot", _svc_publish_snapshot)
    hass.services.async_register(DOMAIN, "prune_unassigned", _svc_prune_unassigned)
    hass.services.async_register(DOMAIN, "dump_state", _svc_dump_state)
    hass.services.async_register(DOMAIN, "republish_reload_all", _svc_republish_reload_all)

    async def _svc_dump_store(call):
        publish = bool(call.data.get("publish", False)) if hasattr(call, "data") else False
        topic = call.data.get("topic") if hasattr(call, "data") else None
        _LOGGER.debug("svc:dump_store publish=%s topic=%s", publish, topic)
        await bridge.async_dump_store(publish=publish, topic=topic)
    hass.services.async_register(DOMAIN, "dump_store", _svc_dump_store)

    async def _svc_dump_runtime_cfg(call):
        publish = bool(call.data.get("publish", False)) if hasattr(call, "data") else False
        topic = call.data.get("topic") if hasattr(call, "data") else None
        _LOGGER.debug("svc:dump_runtime_cfg publish=%s topic=%s", publish, topic)
        await bridge.async_dump_runtime_cfg(publish=publish, topic=topic)
    hass.services.async_register(DOMAIN, "dump_runtime_cfg", _svc_dump_runtime_cfg)

    async def _svc_dump_device_config(call):
        device_id = call.data.get("device_id") if hasattr(call, "data") else None
        if not isinstance(device_id, str) or not device_id:
            _LOGGER.warning("svc:dump_device_config missing device_id")
            return
        publish = bool(call.data.get("publish", False)) if hasattr(call, "data") else False
        topic = call.data.get("topic") if hasattr(call, "data") else None
        _LOGGER.debug("svc:dump_device_config device_id=%s publish=%s topic=%s", device_id, publish, topic)
        await bridge.async_dump_device_config(device_id=device_id, publish=publish, topic=topic)
    hass.services.async_register(DOMAIN, "dump_device_config", _svc_dump_device_config)

    async def _svc_set_device_profile(call):
        dev_id = call.data.get("device_id")
        profile = call.data.get("profile")
        if not isinstance(dev_id, str) or not dev_id:
            _LOGGER.warning("svc:set_device_profile missing device_id")
            return
        if isinstance(profile, str):
            try:
                profile = json.loads(profile)
            except Exception:
                _LOGGER.warning("svc:set_device_profile invalid JSON string for %s", dev_id)
                return
        if not isinstance(profile, dict):
            _LOGGER.warning("svc:set_device_profile expects dict JSON for %s", dev_id)
            return
        # Persist into HA Store (canonical), which also mirrors to options
        try:
            helper = StorageHelper(hass, entry)
            await helper.async_init()
            profs = dict(helper.storage.get("profiles") or {})
            profs[dev_id] = profile
            await helper.persist_profiles(profs)
            _LOGGER.debug("svc:set_device_profile persisted to Store for %s (keys=%s)", dev_id, list(profs.keys()))
        except Exception:
            _LOGGER.exception("svc:set_device_profile: failed to persist Store for %s", dev_id)
        # Schedule republish+reload so device sees changes quickly
        bridge.schedule_republish_reload("set_device_profile")

    hass.services.async_register(DOMAIN, "set_device_profile", _svc_set_device_profile)

    # Schema for notify service (domain: ha_mqtt_dash, service: notify)
    _NOTIFY_SCHEMA = vol.Schema({
        vol.Optional("device_id"): cv.string,  # direct mqttdash device id
        vol.Optional("ha_device"): cv.string,  # HA device registry id (via device selector)
        vol.Required("message"): cv.string,
        vol.Optional("title"): cv.string,
    })

    async def _svc_notify(call):
        dev_id = call.data.get("device_id") if hasattr(call, "data") else None
        message = call.data.get("message") if hasattr(call, "data") else None
        title = call.data.get("title") if hasattr(call, "data") else None
        # Resolve via HA device selector if direct device_id not provided
        if (not isinstance(dev_id, str)) or (not dev_id.strip()):
            ha_dev = call.data.get("ha_device") if hasattr(call, "data") else None
            if isinstance(ha_dev, str) and ha_dev.strip():
                try:
                    dev_reg = async_get_dev_reg(hass)
                    dev = dev_reg.async_get(ha_dev)
                    if dev and dev.identifiers:
                        for dom, ident in dev.identifiers:
                            if dom == DOMAIN and isinstance(ident, str) and ident.strip():
                                dev_id = ident
                                break
                except Exception:
                    pass
        await bridge.async_send_notification((dev_id or ""), (message or ""), title)
    hass.services.async_register(DOMAIN, "notify", _svc_notify, schema=_NOTIFY_SCHEMA)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("ha_mqtt_dash: platforms forwarded: %s", PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    bridge: MqttBridge = hass.data[DOMAIN].pop(entry.entry_id)
    await bridge.async_unload()
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device) -> bool:
    """Support HA 'Delete device' from the device page.

    When invoked, purge retained topics and remove the device from options/Store.
    """
    try:
        # Find our identifier for this device
        dev_id = None
        for domain, ident in (device.identifiers or set()):
            if domain == DOMAIN and isinstance(ident, str):
                dev_id = ident
                break
        if not dev_id:
            return False
        bridge: MqttBridge | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not bridge:
            return False
        # Best-effort capture GUID from options/devices
        try:
            opts = dict(entry.options or {})
            devs = list(opts.get("devices", []) or [])
            guid = None
            for d in devs:
                if d.get("device_id") == dev_id:
                    guid = d.get("guid")
                    break
            # Persist a purged marker to HA Store to prevent auto-recreation on hello
            try:
                helper = StorageHelper(hass, entry)
                await helper.async_init()
                await helper.add_purged(device_id=dev_id, guid=(guid if isinstance(guid, str) else None))
            except Exception:
                _LOGGER.debug("async_remove_config_entry_device: could not persist purged marker", exc_info=True)
        except Exception:
            _LOGGER.debug("async_remove_config_entry_device: failed while extracting guid", exc_info=True)
        await bridge.async_purge_device(dev_id)
        return True
    except Exception:
        _LOGGER.exception("async_remove_config_entry_device failed")
        return False
