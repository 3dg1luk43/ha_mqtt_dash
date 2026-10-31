from __future__ import annotations
from ..const import CONF_DEVICES
from ..entities.brightness import BrightnessNumber, ScreensaverNumber
from ..entities.battery_care import ChargeLevelNumber


async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.options or entry.data or {}
    devices = data.get(CONF_DEVICES, []) or []

    ents = []
    for d in devices:
        dev_id = d.get("device_id")
        if not dev_id:
            continue
        ents.append(BrightnessNumber(hass, entry, dev_id))
        ents.append(ScreensaverNumber(hass, entry, dev_id))
        ents.append(ChargeLevelNumber(hass, entry, dev_id, "start"))
        ents.append(ChargeLevelNumber(hass, entry, dev_id, "stop"))
    async_add_entities(ents)

