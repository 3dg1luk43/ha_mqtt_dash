from __future__ import annotations
from typing import Any
from ..const import DOMAIN, CONF_DEVICES
from ..entities.device_sensors import BatteryLevelSensor


async def async_setup_entry(hass, entry, async_add_entities):
	data = entry.options or entry.data or {}
	devices = data.get(CONF_DEVICES, []) or []
	ents = []
	for d in devices:
		dev_id = d.get("device_id")
		if not dev_id:
			continue
		ents.append(BatteryLevelSensor(hass, entry, dev_id))
		# Charging moved to binary_sensor platform for compatibility
		# (SensorDeviceClass.BATTERY_CHARGING may not exist in your HA version)
	async_add_entities(ents, update_before_add=False)

