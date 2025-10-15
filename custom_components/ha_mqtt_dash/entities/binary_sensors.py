from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass  # type: ignore
from homeassistant.core import callback  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from ..const import DOMAIN
from homeassistant.components import mqtt  # type: ignore
from typing import Optional, Callable


class ChargingBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=f"{device_id}")

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(identifiers={(DOMAIN, self._device_id)}, name=f"{self._device_id}")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}:{self._device_id}:charging"

    @property
    def is_on(self) -> bool | None:
        st = self._hass.data.get(DOMAIN, {}).get("telemetry", {}).get(self._device_id, {})
        v = st.get("charging")
        if v is None:
            return None
        return bool(v)


class OnlineBinarySensor(BinarySensorEntity):
    """Binary sensor that reflects device MQTT LWT online/offline status."""

    _attr_has_entity_name = True
    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False

    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=f"{device_id}")
        self._is_online: Optional[bool] = None
        self._unsub: Optional[Callable[[], None]] = None
        # Fixed topic per device in integration namespace
        self._status_topic = f"mqttdash/dev/{device_id}/status"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(identifiers={(DOMAIN, self._device_id)}, name=f"{self._device_id}")

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}:{self._device_id}:online"

    @property
    def is_on(self) -> bool | None:
        return self._is_online

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _cb(msg) -> None:  # type: ignore
            raw = getattr(msg, "payload", None)
            if isinstance(raw, bytes):
                payload = raw.decode("utf-8", "ignore")
            elif isinstance(raw, str):
                payload = raw
            else:
                payload = "" if raw is None else str(raw)
            payload = payload.strip().lower()

            if payload in ("online", "offline"):
                online = payload == "online"
            else:
                online = None

            if online is None:
                if self._is_online is not None:
                    self._is_online = None
                    self.async_write_ha_state()
                return

            if self._is_online != online:
                self._is_online = online
                self.async_write_ha_state()

        # Subscribe to retained status; we'll immediately get retained value if present
        self._unsub = await mqtt.async_subscribe(self._hass, self._status_topic, _cb)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            try:
                self._unsub()
            finally:
                self._unsub = None
