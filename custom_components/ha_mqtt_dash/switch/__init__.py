from __future__ import annotations
from ..const import CONF_DEVICES
from ..entities.keep_awake import KeepAwakeSwitch
from ..entities.battery_care import BatteryCareSwitch


async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.options or entry.data or {}
    devices = data.get(CONF_DEVICES, []) or []
    ents = []
    for d in devices:
        dev_id = d.get("device_id")
        if not dev_id:
            continue
        ents.append(KeepAwakeSwitch(hass, entry, dev_id))
        ents.append(BatteryCareSwitch(hass, entry, dev_id))
    async_add_entities(ents)
