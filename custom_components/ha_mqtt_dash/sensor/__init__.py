from __future__ import annotations
from ..const import CONF_DEVICES
from ..entities.device_sensors import BatteryLevelSensor
from ..entities.battery_care import BatteryCareStatusSensor


async def async_setup_entry(hass, entry, async_add_entities):
	data = entry.options or entry.data or {}
	devices = data.get(CONF_DEVICES, []) or []
	ents = []
	for d in devices:
		dev_id = d.get("device_id")
		if not dev_id:
			continue
		ents.append(BatteryLevelSensor(hass, entry, dev_id))
		ents.append(BatteryCareStatusSensor(hass, entry, dev_id))
		# Charging moved to binary_sensor platform for compatibility
		# (SensorDeviceClass.BATTERY_CHARGING may not exist in your HA version)
	async_add_entities(ents, update_before_add=False)

