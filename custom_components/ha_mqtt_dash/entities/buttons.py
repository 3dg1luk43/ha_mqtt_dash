from __future__ import annotations
from homeassistant.components.button import ButtonEntity  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from ..const import DOMAIN


class _BaseBtn(ButtonEntity):
    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=f"{device_id}")

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(identifiers={(DOMAIN, self._device_id)}, name=f"{self._device_id}")


class ReloadDeviceButton(_BaseBtn):
    _attr_name = "Reload Device"
    _attr_icon = "mdi:refresh"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}:{self._device_id}:btn_reload"

    async def async_press(self) -> None:
        bridge = self._hass.data[DOMAIN][self._entry.entry_id]
        # Republish configs and nudge device to reload
        await bridge.async_publish_all_configs()
        await bridge.async_publish_device_action(self._device_id, action="reload")
