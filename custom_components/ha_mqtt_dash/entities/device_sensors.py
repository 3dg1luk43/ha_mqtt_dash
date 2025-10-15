from __future__ import annotations
from typing import Any
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from ..const import DOMAIN


class _BaseDeviceEntity(SensorEntity):
    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=f"{device_id}")

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(identifiers={(DOMAIN, self._device_id)}, name=f"{self._device_id}")


class BatteryLevelSensor(_BaseDeviceEntity):
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}:{self._device_id}:battery"

    @property
    def native_value(self) -> Any:
        # Filled via telemetry that bridge caches in hass.data[DOMAIN]["telemetry"]
        st = self._hass.data.get(DOMAIN, {}).get("telemetry", {}).get(self._device_id, {})
        return st.get("battery")
