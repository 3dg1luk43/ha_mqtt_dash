"""One notify entity per panel: notify.send_message shows a popup on the iPad.

Replaces the older per-panel notify.mqttdash_<id> services. The MQTT payload
is unchanged: {"message": ..., "title"?: ...} on mqttdash/dev/<id>/notify.
"""
from __future__ import annotations

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore

from .const import CONF_DEVICES, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.options or entry.data or {}
    ents = [PanelNotifyEntity(hass, entry, d["device_id"])
            for d in (data.get(CONF_DEVICES, []) or []) if isinstance(d, dict) and d.get("device_id")]
    async_add_entities(ents)


class PanelNotifyEntity(NotifyEntity):
    _attr_has_entity_name = True
    _attr_name = None  # the panel itself: notify.<panel>
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}:{device_id}:notify"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=device_id)

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        bridge = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if bridge:
            await bridge.async_send_notification(self._device_id, message, title)
