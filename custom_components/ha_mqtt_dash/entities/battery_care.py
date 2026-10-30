"""Per-panel wake / battery-care entities."""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.button import ButtonEntity  # type: ignore
from homeassistant.components.number import NumberEntity, NumberMode  # type: ignore
from homeassistant.components.sensor import SensorEntity  # type: ignore
from homeassistant.components.switch import SwitchEntity  # type: ignore
from homeassistant.const import EntityCategory, PERCENTAGE  # type: ignore
from homeassistant.core import callback  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_connect  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore

from ..battery_care import SIGNAL_BATTERY_CARE_UPDATED
from ..const import DOMAIN


class _PanelEntity:
    """Shared device binding + access to the bridge."""

    _attr_has_entity_name = True

    def _init_panel(self, hass, entry, device_id: str, key: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}:{device_id}:{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=device_id)

    @property
    def _bridge(self):
        return self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id)


class _CareListener(_PanelEntity):
    """Refresh when battery care state for this panel changes."""

    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:  # type: ignore[override]
        await super().async_added_to_hass()  # type: ignore[misc]

        @callback
        def _upd(device_id: str) -> None:
            if device_id == self._device_id:
                self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self._hass, SIGNAL_BATTERY_CARE_UPDATED, _upd))


class WakeScreenButton(_PanelEntity, ButtonEntity):
    """Turn the panel's screen on (works while it's asleep via the background link)."""

    _attr_name = "Wake screen"
    _attr_icon = "mdi:tablet-dashboard"

    def __init__(self, hass, entry, device_id: str) -> None:
        self._init_panel(hass, entry, device_id, "btn_wake")

    async def async_press(self) -> None:
        if self._bridge:
            await self._bridge.async_send_device_request(self._device_id, "wake")


class CheckBatteryButton(_PanelEntity, ButtonEntity):
    """Ask the panel for a fresh battery reading without waking the screen."""

    _attr_name = "Check battery"
    _attr_icon = "mdi:battery-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, entry, device_id: str) -> None:
        self._init_panel(hass, entry, device_id, "btn_check_battery")

    async def async_press(self) -> None:
        if self._bridge:
            await self._bridge.async_send_device_request(self._device_id, "report")


class BatteryCareSwitch(_CareListener, SwitchEntity):
    _attr_name = "Battery care"
    _attr_icon = "mdi:battery-heart-variant"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass, entry, device_id: str) -> None:
        self._init_panel(hass, entry, device_id, "battery_care")

    @property
    def is_on(self) -> Optional[bool]:
        b = self._bridge
        return bool(b.battery.settings(self._device_id)["enabled"]) if b else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._bridge:
            await self._bridge.battery.async_update_settings(self._device_id, {"enabled": True})
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._bridge:
            await self._bridge.battery.async_update_settings(self._device_id, {"enabled": False})
            self.async_write_ha_state()


class ChargeLevelNumber(_CareListener, NumberEntity):
    """Charge start / stop level (%)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER

    def __init__(self, hass, entry, device_id: str, which: str) -> None:
        self._which = which  # "start" | "stop"
        self._init_panel(hass, entry, device_id, f"charge_{which}")
        if which == "start":
            self._attr_name = "Charge start level"
            self._attr_icon = "mdi:battery-charging-30"
            self._attr_native_min_value, self._attr_native_max_value = 10, 90
        else:
            self._attr_name = "Charge stop level"
            self._attr_icon = "mdi:battery-charging-80"
            self._attr_native_min_value, self._attr_native_max_value = 30, 100

    @property
    def native_value(self) -> Optional[float]:
        b = self._bridge
        return float(b.battery.settings(self._device_id)[self._which]) if b else None

    async def async_set_native_value(self, value: float) -> None:
        if self._bridge:
            await self._bridge.battery.async_update_settings(self._device_id, {self._which: int(value)})
            self.async_write_ha_state()


class BatteryCareStatusSensor(_CareListener, SensorEntity):
    """What battery care is doing right now and why."""

    _attr_name = "Battery care status"
    _attr_icon = "mdi:battery-clock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, entry, device_id: str) -> None:
        self._init_panel(hass, entry, device_id, "battery_care_status")

    @property
    def native_value(self) -> Optional[str]:
        b = self._bridge
        return b.battery.status(self._device_id).get("state") if b else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        b = self._bridge
        if not b:
            return {}
        st = b.battery.status(self._device_id)
        return {k: v for k, v in st.items() if k != "state" and v is not None}
