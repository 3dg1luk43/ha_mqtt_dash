from __future__ import annotations

from typing import Any, Callable, Dict, List

from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore

from .const import DOMAIN, CONF_DEVICES  # type: ignore
from .mqtt_bridge import MqttBridge  # type: ignore
import voluptuous as vol  # type: ignore
import homeassistant.helpers.config_validation as cv  # type: ignore


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> bool:  # type: ignore[no-untyped-def]
    """Register per-device notify services under the notify domain.

    This uses dynamic service registration rather than BaseNotificationService, to keep
    the implementation lightweight and config-entry-driven. Each device becomes a
    service "notify.mqttdash_<device_id>" with kwargs: message (required), title (optional).
    """
    bridge: MqttBridge = hass.data[DOMAIN][entry.entry_id]

    # Track removal callbacks so unload cleans up our services
    remove_callbacks: List[Callable[[], None]] = []

    def _register_for_device(device_id: str) -> None:
        svc_name = f"mqttdash_{device_id.replace('-', '_') }"

        # Require message, allow optional title
        schema = vol.Schema({
            vol.Required("message"): cv.string,
            vol.Optional("title"): cv.string,
        })

        async def _handler(call):
            # call.data: { "message": str, "title": str? }
            msg = call.data.get("message") if hasattr(call, "data") else None
            ttl = call.data.get("title") if hasattr(call, "data") else None
            await bridge.async_send_notification(device_id, msg or "", ttl)

        hass.services.async_register("notify", svc_name, _handler, schema=schema)

        def _remove() -> None:
            try:
                hass.services.async_remove("notify", svc_name)
            except Exception:
                pass

        remove_callbacks.append(_remove)

    try:
        devices: List[Dict[str, Any]] = list(bridge.cfg.get(CONF_DEVICES, []) or [])
        for d in devices:
            did = (d.get("device_id") or "").strip()
            if did:
                _register_for_device(did)
    except Exception:  # pragma: no cover - defensive around user configs
        # If anything goes wrong, we still succeed without registering services
        pass

    hass.data.setdefault(DOMAIN, {}).setdefault("notify_unsubs", {})[entry.entry_id] = remove_callbacks
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # type: ignore[no-untyped-def]
    """Remove any dynamically registered notify services for this entry."""
    removes = hass.data.get(DOMAIN, {}).get("notify_unsubs", {}).pop(entry.entry_id, [])
    for r in list(removes or []):
        try:
            r()
        except Exception:
            pass
    return True
