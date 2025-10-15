from __future__ import annotations
from typing import Any
from homeassistant.components.number import NumberEntity  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_connect  # type: ignore
from ..const import DOMAIN, CONF_DEVICES, SIGNAL_DEVICE_SETTINGS_UPDATED


class BrightnessNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Brightness"
    _attr_native_min_value = 0.05
    _attr_native_max_value = 1.0
    _attr_native_step = 0.05
    _attr_mode = "slider"

    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=f"{device_id}")
        self._cached_value: float | None = None
        # Hydrate from Store via bridge if available
        try:
            bridge = hass.data[DOMAIN][entry.entry_id]
            cur = bridge.get_device_settings(device_id)
            if isinstance(cur, dict):
                bval = cur.get("brightness")
                if isinstance(bval, (int, float)):
                    f = float(bval)
                    if f < 0.05: f = 0.05
                    if f > 1.0: f = 1.0
                    self._cached_value = f
        except Exception:
            pass
        self._unsub = async_dispatcher_connect(
            hass, SIGNAL_DEVICE_SETTINGS_UPDATED, self._on_settings_update
        )

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(identifiers={(DOMAIN, self._device_id)}, name=f"{self._device_id}")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}:{self._device_id}:brightness"

    @property
    def native_value(self) -> float | None:
        if self._cached_value is not None:
            return self._cached_value
        devs = (self._entry.options or {}).get(CONF_DEVICES, [])
        for d in devs:
            if d.get("device_id") == self._device_id:
                val = d.get("device", {}).get("brightness") or d.get("brightness")
                try:
                    f = float(val)
                    if f < 0.05: f = 0.05
                    if f > 1.0: f = 1.0
                    return f
                except Exception:
                    break
        return 0.35

    async def async_set_native_value(self, value: float) -> None:
        v = value
        if v < 0.05: v = 0.05
        if v > 1.0: v = 1.0
        bridge = self._hass.data[DOMAIN][self._entry.entry_id]
        await bridge.async_publish_device_settings(self._device_id, brightness=v)
        self._cached_value = v
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
        val = settings.get("brightness")
        try:
            if val is not None:
                f = float(val)
                if f < 0.05: f = 0.05
                if f > 1.0: f = 1.0
                self._cached_value = f
                # Ensure thread-safety: schedule state write in event loop
                self._hass.add_job(self.async_write_ha_state)
        except Exception:
            return
