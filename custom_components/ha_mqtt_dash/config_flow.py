"""Setup and options for iPad MQTT Dashboard.

Setup takes no input: panels register themselves when the app first connects
(its hello), and their layouts are designed in the dashboard editor. The
options hold the editor link (+ optional sidebar entry), battery care and
YouTube casting.
"""
from __future__ import annotations

import voluptuous as vol  # type: ignore
from homeassistant import config_entries  # type: ignore
from homeassistant.core import callback  # type: ignore
from homeassistant.helpers import selector  # type: ignore

from .const import DOMAIN, CONF_DEVICES, CONF_PROFILES, CONF_EDITOR_SIDEBAR, CONF_YT_CAST


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc]
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
        return self.async_create_entry(title="iPad MQTT Dashboard", data={CONF_DEVICES: [], CONF_PROFILES: {}})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Dashboard editor link, battery care and YouTube casting."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["editor", "battery", "cast"])

    # Link to the dashboard-editor panel; its sidebar entry is optional (off by
    # default: the editor is used rarely).
    async def async_step_editor(self, user_input=None):
        current = bool(self._entry.options.get(CONF_EDITOR_SIDEBAR, False))
        if user_input is not None:
            wanted = bool(user_input.get(CONF_EDITOR_SIDEBAR, current))
            if wanted == current:
                return await self.async_step_init()
            # Profiles live in the Store; leave them out so a stale options copy
            # can't overwrite what the editor deployed.
            opts = {k: v for k, v in (self._entry.options or {}).items() if k != CONF_PROFILES}
            return self.async_create_entry(title="", data={**opts, CONF_EDITOR_SIDEBAR: wanted})
        schema = vol.Schema({
            vol.Optional(CONF_EDITOR_SIDEBAR, default=current): selector.BooleanSelector(),
        })
        return self.async_show_form(step_id="editor", data_schema=schema,
                                    description_placeholders={"url": "/mqttdash-editor"})

    # YouTube casting: every panel is a cast target in the YouTube app (on by default)
    async def async_step_cast(self, user_input=None):
        current = bool(self._entry.options.get(CONF_YT_CAST, True))
        if user_input is not None:
            wanted = bool(user_input.get(CONF_YT_CAST, current))
            if wanted == current:
                return await self.async_step_init()
            opts = {k: v for k, v in (self._entry.options or {}).items() if k != CONF_PROFILES}
            return self.async_create_entry(title="", data={**opts, CONF_YT_CAST: wanted})
        schema = vol.Schema({
            vol.Optional(CONF_YT_CAST, default=current): selector.BooleanSelector(),
        })
        return self.async_show_form(step_id="cast", data_schema=schema)

    # Battery care: pick the charger plug + charge window per device. Saved to
    # the Store (not options) and ends with an abort-style confirmation so it
    # never rewrites the whole options payload.
    async def async_step_battery(self, user_input=None):
        devices = [d.get("device_id") for d in (self._entry.options.get(CONF_DEVICES) or [])
                   if isinstance(d, dict) and d.get("device_id")]
        if not devices:
            return self.async_abort(reason="no_devices")
        if user_input is None and len(devices) == 1:
            self._battery_device = devices[0]
            return await self.async_step_battery_device()
        schema = vol.Schema({
            vol.Required("device_id", default=devices[0]): selector.SelectSelector(
                selector.SelectSelectorConfig(options=devices)),
        })
        if user_input is None:
            return self.async_show_form(step_id="battery", data_schema=schema)
        self._battery_device = user_input["device_id"]
        return await self.async_step_battery_device()

    async def async_step_battery_device(self, user_input=None):
        bridge = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if bridge is None:
            return self.async_abort(reason="not_loaded")
        dev = getattr(self, "_battery_device", "")
        cfg = bridge.battery.settings(dev)
        schema = vol.Schema({
            vol.Optional("enabled", default=bool(cfg["enabled"])): selector.BooleanSelector(),
            vol.Optional("charger", description={"suggested_value": cfg["charger"] or None}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "light", "input_boolean"])),
            vol.Optional("start", default=cfg["start"]): selector.NumberSelector(selector.NumberSelectorConfig(
                min=10, max=90, step=5, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)),
            vol.Optional("stop", default=cfg["stop"]): selector.NumberSelector(selector.NumberSelectorConfig(
                min=30, max=100, step=5, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)),
            vol.Optional("presence", description={"suggested_value": cfg["presence"] or None}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["person", "device_tracker"], multiple=True)),
        })
        if user_input is None:
            tel = (bridge._telemetry or {}).get(dev, {})
            return self.async_show_form(step_id="battery_device", data_schema=schema, description_placeholders={
                "device": dev, "battery": str(tel.get("battery", "?")),
                "state": bridge.battery.status(dev).get("state", "disabled"),
            })
        await bridge.battery.async_update_settings(dev, {
            "enabled": bool(user_input.get("enabled", False)),
            "charger": user_input.get("charger") or "",
            "start": user_input.get("start", cfg["start"]),
            "stop": user_input.get("stop", cfg["stop"]),
            "presence": user_input.get("presence") or [],
        })
        return self.async_abort(reason="battery_saved")
