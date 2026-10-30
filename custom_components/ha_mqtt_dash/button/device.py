from __future__ import annotations
from ..const import CONF_DEVICES
from ..entities.buttons import ReloadDeviceButton
from ..entities.battery_care import WakeScreenButton, CheckBatteryButton


async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.options or entry.data or {}
    devices = data.get(CONF_DEVICES, []) or []
    ents = []
    for d in devices:
        dev_id = d.get("device_id")
        if not dev_id:
            continue
        ents.append(ReloadDeviceButton(hass, entry, dev_id))
        ents.append(WakeScreenButton(hass, entry, dev_id))
        ents.append(CheckBatteryButton(hass, entry, dev_id))
    async_add_entities(ents, update_before_add=False)

