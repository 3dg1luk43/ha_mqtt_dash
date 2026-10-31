from __future__ import annotations
from ..const import CONF_DEVICES
from ..entities.video_player import PanelVideoPlayer


async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.options or entry.data or {}
    ents = [PanelVideoPlayer(hass, entry, d["device_id"]) for d in (data.get(CONF_DEVICES) or []) if isinstance(d, dict) and d.get("device_id")]
    async_add_entities(ents, update_before_add=False)
