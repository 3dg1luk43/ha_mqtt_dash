from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore
from .const import DOMAIN, CONF_EDITOR_SIDEBAR
import json
from .storage import StorageHelper
import voluptuous as vol  # type: ignore
import homeassistant.helpers.config_validation as cv  # type: ignore
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg  # type: ignore
from homeassistant.helpers import entity_registry as er  # type: ignore
from homeassistant.exceptions import ServiceValidationError  # type: ignore

PLATFORMS = ["sensor", "binary_sensor", "switch", "select", "number", "button", "notify", "media_player"]
from .mqtt_bridge import MqttBridge
from .editor_panel import async_setup_editor, async_remove_editor_panel, PANEL_URL

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _LOGGER.debug("ha_mqtt_dash: async_setup called")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("ha_mqtt_dash: async_setup_entry starting")
    hass.data.setdefault(DOMAIN, {})
    bridge = MqttBridge(hass, entry)
    # Helper: ensure a HA device exists in the registry for each configured device_id.
    # This makes entities show under a device even if created before first hello.
    def _ensure_devices_in_registry(cfg: dict) -> None:
        try:
            dev_reg = async_get_dev_reg(hass)
            devices = list((cfg or {}).get("devices", []) or [])
            for d in devices:
                did = (d or {}).get("device_id")
                if isinstance(did, str) and did.strip():
                    dev_reg.async_get_or_create(
                        config_entry_id=entry.entry_id,
                        identifiers={(DOMAIN, did)},
                        name=did,
                        # "Visit" link on the device page opens the dashboard editor
                        configuration_url=f"homeassistant://{PANEL_URL}",
                    )
        except Exception:
            _LOGGER.debug("ensure_devices_in_registry: skipped (registry op failed)", exc_info=True)
    # Register update listener BEFORE bridge async_setup so any options writes during
    # storage initialization are observed by the bridge.
    async def _on_update(hass: HomeAssistant, updated: ConfigEntry):
        _LOGGER.debug("ha_mqtt_dash: options updated -> forwarding to bridge")
        await bridge.async_options_updated(updated)
        opts = {**(updated.data or {}), **(updated.options or {})}
        try:
            _ensure_devices_in_registry(opts)
        except Exception:
            _LOGGER.debug("post-update ensure_devices_in_registry failed", exc_info=True)
        try:
            await async_setup_editor(hass, sidebar=bool((updated.options or {}).get(CONF_EDITOR_SIDEBAR, False)))
        except Exception:
            _LOGGER.exception("dashboard editor panel update failed")
    entry.async_on_unload(entry.add_update_listener(_on_update))

    await bridge.async_setup()
    hass.data[DOMAIN][entry.entry_id] = bridge
    _LOGGER.debug("ha_mqtt_dash: bridge setup complete; registering services")
    try:
        await async_setup_editor(hass, sidebar=bool((entry.options or {}).get(CONF_EDITOR_SIDEBAR, False)))
    except Exception:
        _LOGGER.exception("dashboard editor panel setup failed")
    # Ensure device objects exist up front so UI groups entities under a device immediately
    try:
        cfg_now = {**(entry.data or {}), **(entry.options or {})}
        _ensure_devices_in_registry(cfg_now)
    except Exception:
        _LOGGER.debug("initial ensure_devices_in_registry failed", exc_info=True)

    _register_services(hass)
    _migrate_entity_ids(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("ha_mqtt_dash: platforms forwarded: %s", PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async_remove_editor_panel(hass)
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


def _bridge_for(hass: HomeAssistant) -> MqttBridge | None:
    for b in (hass.data.get(DOMAIN) or {}).values():
        if isinstance(b, MqttBridge):
            return b
    return None


# Entity IDs that changed with the 0.6.0 names; renamed only while still the
# old default and the new one is free (user-chosen IDs are left alone).
_RENAMED_SUFFIXES = {":btn_reload": ("_reload_device", "_reload")}


def _migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(reg, entry.entry_id):
        for uid_suffix, (old, new) in _RENAMED_SUFFIXES.items():
            if not ent.unique_id.endswith(uid_suffix) or not ent.entity_id.endswith(old):
                continue
            target = ent.entity_id[: -len(old)] + new
            if reg.async_get(target) is None:
                reg.async_update_entity(ent.entity_id, new_entity_id=target)
                _LOGGER.info("renamed %s to %s", ent.entity_id, target)


def _panel_id(hass: HomeAssistant, data: dict) -> str | None:
    """Panel id from a device-selector target (HA device id) or a plain panel id."""
    ha_device = data.get("device")
    if isinstance(ha_device, list):
        ha_device = ha_device[0] if ha_device else None
    if isinstance(ha_device, str) and ha_device:
        dev = async_get_dev_reg(hass).async_get(ha_device)
        for dom, ident in (dev.identifiers if dev else set()):
            if dom == DOMAIN and isinstance(ident, str) and ident.strip():
                return ident
    pid = data.get("device_id")
    return pid.strip() if isinstance(pid, str) and pid.strip() else None


_RELOAD_SCHEMA = vol.Schema({})
_SET_PROFILE_SCHEMA = vol.Schema({
    vol.Optional("device"): vol.Any(cv.string, [cv.string]),
    vol.Optional("device_id"): cv.string,  # panel id; older automations
    vol.Required("profile"): vol.Any(dict, cv.string),
})


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "reload"):
        return

    async def _svc_reload(call):
        bridge = _bridge_for(hass)
        if bridge:
            bridge.schedule_republish_reload("service")

    async def _svc_set_device_profile(call):
        bridge = _bridge_for(hass)
        dev_id = _panel_id(hass, call.data)
        profile = call.data.get("profile")
        if not bridge or not dev_id:
            raise ServiceValidationError("Pick an iPad MQTT Dashboard panel")
        if isinstance(profile, str):
            try:
                profile = json.loads(profile)
            except ValueError as err:
                raise ServiceValidationError(f"The profile is not valid JSON: {err}") from err
        if not isinstance(profile, dict):
            raise ServiceValidationError("The profile must be a JSON object")
        profs = dict(bridge._storage_helper.storage.get("profiles") or {})
        profs[dev_id] = profile
        await bridge._storage_helper.persist_profiles(profs)
        bridge.schedule_republish_reload("set_device_profile")

    hass.services.async_register(DOMAIN, "reload", _svc_reload, schema=_RELOAD_SCHEMA)
    hass.services.async_register(DOMAIN, "set_device_profile", _svc_set_device_profile, schema=_SET_PROFILE_SCHEMA)
