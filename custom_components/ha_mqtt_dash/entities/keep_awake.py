from __future__ import annotations
from homeassistant.components.switch import SwitchEntity  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_connect  # type: ignore
from ..const import DOMAIN, SIGNAL_DEVICE_SETTINGS_UPDATED

KEEP_AWAKE_KEY = "keep_awake"


class KeepAwakeSwitch(SwitchEntity):
    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_has_entity_name = True
        self._attr_name = "Keep Awake"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=f"{device_id}")
        # Initial state
        self._is_on_cache = True
        try:
            bridge = hass.data[DOMAIN][entry.entry_id]
            cur = bridge.get_device_settings(device_id)
            if isinstance(cur, dict) and KEEP_AWAKE_KEY in cur:
                self._is_on_cache = bool(cur.get(KEEP_AWAKE_KEY))
        except Exception:
            pass
        self._unsub = async_dispatcher_connect(hass, SIGNAL_DEVICE_SETTINGS_UPDATED, self._on_settings_update)

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}:{self._device_id}:keep_awake"

    @property
    def is_on(self) -> bool:
        return bool(self._is_on_cache)

    async def async_turn_on(self, **kwargs) -> None:
        await self._publish_settings(keep_awake=True)
        self._is_on_cache = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._publish_settings(keep_awake=False)
        self._is_on_cache = False
        self.async_write_ha_state()

    async def _publish_settings(self, **patch) -> None:
        bridge = self._hass.data[DOMAIN][self._entry.entry_id]
        await bridge.async_publish_device_settings(self._device_id, **patch)

    async def async_will_remove_from_hass(self) -> None:
        try:
            if self._unsub:
                self._unsub()
        except Exception:
            pass

    def _on_settings_update(self, device_id: str, settings: dict) -> None:
        if device_id != self._device_id:
            return
        if KEEP_AWAKE_KEY in settings:
            self._is_on_cache = bool(settings.get(KEEP_AWAKE_KEY))
            self._hass.add_job(self.async_write_ha_state)
