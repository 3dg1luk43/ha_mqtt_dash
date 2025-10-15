from __future__ import annotations
from homeassistant.components.select import SelectEntity  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_connect  # type: ignore
from ..const import DOMAIN, SIGNAL_DEVICE_SETTINGS_UPDATED


class OrientationSelect(SelectEntity):
    _attr_options = ["auto", "portrait", "landscape"]

    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_has_entity_name = True
        self._attr_name = "Orientation"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=f"{device_id}")
        self._cached: str | None = None
        # Hydrate from Store via bridge if available
        try:
            bridge = hass.data[DOMAIN][entry.entry_id]
            cur = bridge.get_device_settings(device_id)
            val = cur.get("orientation") if isinstance(cur, dict) else None
            if isinstance(val, str) and val in self._attr_options:
                self._cached = val
        except Exception:
            pass
        self._unsub = async_dispatcher_connect(hass, SIGNAL_DEVICE_SETTINGS_UPDATED, self._on_settings_update)

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}:{self._device_id}:orientation"

    @property
    def current_option(self) -> str | None:
        if self._cached:
            return self._cached
        devs = (self._entry.options or {}).get("devices", [])
        for d in devs:
            if d.get("device_id") == self._device_id:
                val = d.get("device", {}).get("orientation") or d.get("orientation")
                if isinstance(val, str):
                    return val
        return "auto"

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        bridge = self._hass.data[DOMAIN][self._entry.entry_id]
        await bridge.async_publish_device_settings(self._device_id, orientation=option)
        self._cached = option
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        try:
            if self._unsub:
                self._unsub()
        except Exception:
            pass

    def _on_settings_update(self, device_id: str, settings: dict) -> None:
        if device_id != self._device_id:
            return
        val = settings.get("orientation")
        if isinstance(val, str) and val in self._attr_options:
            self._cached = val
            # schedule to ensure thread-safety
            self._hass.add_job(self.async_write_ha_state)
