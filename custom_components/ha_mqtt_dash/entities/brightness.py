"""Panel settings as numbers: screen brightness (%) and screensaver timeout (s).

Both are stored in the Store's device settings and published on the panel's
settings topic; the app's own value for brightness is 0.05–1.0.
"""
from __future__ import annotations

from typing import Optional

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode  # type: ignore
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime  # type: ignore
from homeassistant.core import callback  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_connect  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore

from ..const import DOMAIN, SIGNAL_DEVICE_SETTINGS_UPDATED


def percent_from_brightness(v: float) -> float:
    """App brightness 0.05–1.0 → entity percent 5–100."""
    return float(round(max(0.05, min(1.0, float(v))) * 100))


def brightness_from_percent(v: float) -> float:
    return round(max(5.0, min(100.0, float(v))) / 100.0, 2)


class _SettingNumber(NumberEntity):
    """A number backed by one key of the panel's device settings."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_default: Optional[float] = None
    _key = ""            # device-settings key
    _unique_suffix = ""  # unique id suffix (kept from older versions)

    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}:{device_id}:{self._unique_suffix}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=device_id)
        self._value: Optional[float] = None
        bridge = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        cur = bridge.get_device_settings(device_id) if bridge else {}
        if isinstance(cur, dict) and isinstance(cur.get(self._key), (int, float)):
            self._value = self._from_store(cur[self._key])

    def _from_store(self, v: float) -> float:
        return float(v)

    def _to_store(self, v: float):
        return v

    @property
    def native_value(self) -> Optional[float]:
        return self._value if self._value is not None else self._attr_default

    async def async_set_native_value(self, value: float) -> None:
        bridge = self._hass.data[DOMAIN][self._entry.entry_id]
        await bridge.async_publish_device_settings(self._device_id, **{self._key: self._to_store(value)})
        self._value = float(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        @callback
        def _upd(device_id: str, settings: dict) -> None:
            if device_id == self._device_id and isinstance(settings.get(self._key), (int, float)):
                self._value = self._from_store(settings[self._key])
                self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self._hass, SIGNAL_DEVICE_SETTINGS_UPDATED, _upd))


class BrightnessNumber(_SettingNumber):
    _attr_translation_key = "brightness"
    _attr_icon = "mdi:brightness-6"
    _attr_native_min_value = 5
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_default = 35.0
    _key = "brightness"
    _unique_suffix = "brightness"

    def _from_store(self, v: float) -> float:
        return percent_from_brightness(v)

    def _to_store(self, v: float) -> float:
        return brightness_from_percent(v)


class ScreensaverNumber(_SettingNumber):
    """Seconds without a touch before the clock screensaver shows; 0 = off."""

    _attr_translation_key = "screensaver_timeout"
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = 0
    _attr_native_max_value = 3600
    _attr_native_step = 10
    _attr_mode = NumberMode.BOX
    _attr_default = 0.0
    _key = "screensaver_timeout"
    _unique_suffix = "screensaver_timeout"

    def _to_store(self, v: float) -> int:
        return max(0, int(v))
