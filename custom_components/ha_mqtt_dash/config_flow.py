from __future__ import annotations
import json
import logging
import voluptuous as vol  # type: ignore
from homeassistant import config_entries  # type: ignore
from homeassistant.core import callback # type: ignore
from homeassistant.helpers import selector # type: ignore
from .storage import StorageHelper
from .const import (
    DOMAIN,
    CONF_DEVICES, CONF_PROFILES,
    CONF_MIRROR_ENTITIES,
)

STEP_USER = vol.Schema({
    vol.Required("device_id"): str,
})

STEP_PROFILE = vol.Schema({
    vol.Required("profile_name"): str,
    vol.Optional("rows", default=4): vol.All(int, vol.Range(min=1)),
    vol.Optional("cols", default=4): vol.All(int, vol.Range(min=1)),
    vol.Optional("gutter", default=4): vol.All(int, vol.Range(min=0)),
    vol.Optional("padding", default=6): vol.All(int, vol.Range(min=0)),
    vol.Optional("orientation", default="auto"): vol.In(["auto", "portrait", "landscape"]),
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc]
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER)
        # Streamlined onboarding: ask only for device_id, create default profile+device
        dev_id = (user_input.get("device_id") or "").strip()
        if not dev_id:
            # Re-present form if empty
            return self.async_show_form(step_id="user", data_schema=STEP_USER)
        self._data = {}
        self._data[CONF_DEVICES] = [{"device_id": dev_id, "profile": dev_id}]
        # Default profile: welcome banner and a clock widget
        default_profile = {
            "ui": {
                "banner": "Welcome to MQTT dashboard",
                "grid": {"columns": 6, "widget_dimensions": [120, 120], "widget_margins": [5, 5], "widget_size": [1, 1]},
                "widgets": [
                    {"id": "lbl1", "type": "label", "text": "Edit this profile in Home Assistant → Integration Options → Device Profile. Add widgets by entity_id.", "label": "Getting started", "x": 0, "y": 0, "w": 3, "h": 2, "format": {"wrap": True, "textSize": 16}},
                    {"id": "clk1", "type": "clock", "label": "Time", "time_pattern": "HH:MM", "x": 3, "y": 0, "w": 1, "h": 1},
                    {"id": "ph1", "type": "spacer", "x": 4, "y": 0, "w": 1, "h": 1},
                    {"id": "ph2", "type": "spacer", "x": 5, "y": 0, "w": 1, "h": 1},
                    {"id": "ph3", "type": "spacer", "x": 0, "y": 2, "w": 2, "h": 1}
                ]
            }
        }
        self._data[CONF_PROFILES] = {dev_id: default_profile}
        # Create entry immediately; Store persistence will be handled by the bridge/options later
        return self.async_create_entry(title="iPad MQTT Dashboard", data=self._data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options editor: profiles JSON, device→profile assignment, mirror, topics, guide."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self._entry = entry
        self._data: dict = {**entry.data, **entry.options}
        self._profiles: dict = self._data.get(CONF_PROFILES, {})
        self._devices: list = self._data.get(CONF_DEVICES, [])
        self._mirror_entities = list(self._data.get(CONF_MIRROR_ENTITIES, []))
        logging.getLogger(__name__).debug(
            "options_flow:init devices=%d profiles=%d mirror=%d",
            len(self._devices or []), len(self._profiles or {}), len(self._mirror_entities or []),
        )

    def _refresh_from_entry(self):
        # Helper to rehydrate local caches from latest entry state
        self._data = {**self._entry.data, **self._entry.options}
        self._profiles = self._data.get(CONF_PROFILES, {}) or {}
        self._devices = self._data.get(CONF_DEVICES, []) or []

    async def async_step_init(self, user_input=None):
        logging.getLogger(__name__).debug("options_flow:init menu opened")
        # Refresh canonical profiles from Store on menu open
        try:
            helper = StorageHelper(self.hass, self._entry)
            await helper.async_init()
            store_profiles = dict(helper.storage.get(CONF_PROFILES) or {})
            if store_profiles:
                self._profiles = store_profiles
                self._data[CONF_PROFILES] = self._profiles
        except Exception:
            logging.getLogger(__name__).exception("options_flow:init failed to refresh from Store")
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "profiles_device",
                "devices_add",
                "mirror",
            ],
        )

    # Device-specific profile editor
    async def async_step_profiles_device(self, user_input=None):
        _LOGGER = logging.getLogger(__name__)
        # Rehydrate local snapshot from latest entry in case other steps changed it
        self._refresh_from_entry()
        # Always refresh profiles from HA Store so the editor shows latest canonical content
        try:
            helper = StorageHelper(self.hass, self._entry)
            await helper.async_init()
            store_profiles = dict(helper.storage.get(CONF_PROFILES) or {})
            if store_profiles:
                self._profiles = store_profiles
                self._data[CONF_PROFILES] = self._profiles
        except Exception:
            logging.getLogger(__name__).exception("profiles_device: failed to load profiles from Store")

        ids = [d.get("device_id") for d in self._devices if d.get("device_id")]
        if not ids:
            return self.async_abort(reason="no_devices")

        def _schema_with_defaults(dev_id: str, text: str):
            return vol.Schema({
                vol.Required("device_id", default=dev_id): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ids, multiple=False, mode="dropdown")
                ),
                vol.Optional("profile_json", default=text): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
            })

        if user_input is None:
            _LOGGER.debug("profiles_device: presenting form for %d device(s)", len(ids))
            dev_id = ids[0]
            # Enforce device=profile; migrate lone non-matching profile key to device_id
            prof = self._profiles.get(dev_id)
            if not prof:
                # If device has an assigned profile different from device_id and it exists, migrate it
                assigned = None
                for d in (self._devices or []):
                    if d.get("device_id") == dev_id:
                        assigned = d.get("profile")
                        break
                if assigned and assigned != dev_id and assigned in self._profiles:
                    self._profiles[dev_id] = self._profiles.pop(assigned)
                    self._data[CONF_PROFILES] = self._profiles
                    prof = self._profiles.get(dev_id) or {}
                    logging.getLogger(__name__).debug("profiles_device: migrated assigned profile '%s' -> '%s'", assigned, dev_id)
                else:
                    # Otherwise if there is exactly one non-device key, migrate it
                    keys = list(self._profiles.keys())
                    non_dev_keys = [k for k in keys if k != dev_id]
                    if len(non_dev_keys) == 1:
                        moved = non_dev_keys[0]
                        self._profiles[dev_id] = self._profiles.pop(moved)
                        self._data[CONF_PROFILES] = self._profiles
                        prof = self._profiles.get(dev_id) or {}
                        logging.getLogger(__name__).debug("profiles_device: migrated lone profile '%s' -> '%s'", moved, dev_id)
                    else:
                        prof = {}
            prof_name = dev_id
            _LOGGER.debug(
                "profiles_device: selected device=%s profile_key=%s have_profiles=%s keys=%s",
                dev_id, prof_name, bool(self._profiles), list(self._profiles.keys()),
            )
            current = json.dumps(prof, indent=2, ensure_ascii=False)
            help_txt = (
                "Edit the JSON profile for the selected device. Widgets: use entity_id, label, "
                "and layout x,y,w,h (aliases: row/col,rowspan/colspan). Do NOT set topics; the integration adds them.\n\n"
                "Example: {\n  \"grid\": { \"columns\": 4 },\n  \"widgets\": [\n    { \"id\": \"w1\", \"entity_id\": \"light.kitchen\", \"type\": \"light\", \"x\":0,\"y\":0,\"w\":2,\"h\":1 }\n  ]\n}"
            )
            return self.async_show_form(
                step_id="profiles_device",
                data_schema=_schema_with_defaults(dev_id, current),
                description_placeholders={"desc": help_txt},
            )

        dev_id = user_input.get("device_id") or ids[0]
        prof_name = dev_id  # enforce device=profile
        has_profile_field = ("profile_json" in user_input)
        txt_raw = user_input.get("profile_json")
        txt = (txt_raw or "").strip()
        _LOGGER.debug(
            "profiles_device: submit device=%s profile_key=%s keys=%s profile_len=%s",
            dev_id, prof_name, list(user_input.keys()), (len(txt) if isinstance(txt, str) else None),
        )
        existing = self._profiles.get(prof_name) or {}
        try:
            # If field missing or empty, keep existing profile to avoid accidental wipe
            if not has_profile_field:
                parsed = existing
                decided = "keep_existing_missing_field"
            elif txt == "":
                parsed = existing
                decided = "keep_existing_empty"
            elif txt == "{}":
                parsed = {}
                decided = "explicit_clear"
            else:
                parsed = json.loads(txt)
                decided = "parsed_new"
            assert isinstance(parsed, dict)
            # Unwrap a single top-level key (e.g., {"main_panel": { ...profile... }})
            if isinstance(parsed, dict) and len(parsed) == 1:
                only_key = next(iter(parsed))
                inner = parsed.get(only_key)
                if isinstance(inner, dict) and ("ui" in inner or "widgets" in inner or "dashboard" in inner or "grid" in inner):
                    logging.getLogger(__name__).debug(
                        "profiles_device: unwrapping top-level key '%s' for device=%s", only_key, dev_id
                    )
                    parsed = inner
        except Exception:
            _LOGGER.warning("profiles_device: invalid JSON for device %s (len=%d)", dev_id, len(txt))
            help_txt = (
                "Invalid JSON. Fix the profile and try again. Widgets use entity_id and x,y,w,h; topics are auto-generated."
            )
            return self.async_show_form(
                step_id="profiles_device",
                errors={"base": "invalid_json"},
                data_schema=_schema_with_defaults(dev_id, txt),
                description_placeholders={"desc": help_txt},
            )

        if not prof_name:
            prof_name = dev_id
        # Detect overlapping widgets prior to saving; if overlaps, re-present form with warning.
        overlaps: list[str] = []
        norm = []  # keep for later debug
        try:
            widgets_list = []
            if isinstance(parsed.get("widgets"), list):
                widgets_list = list(parsed.get("widgets") or [])
            elif isinstance(parsed.get("ui"), dict) and isinstance(parsed.get("ui", {}).get("widgets"), list):
                widgets_list = list(parsed.get("ui", {}).get("widgets") or [])
            for w in widgets_list:
                if not isinstance(w, dict):
                    continue
                ent = (w.get("entity_id") or w.get("entity") or "").strip()
                x = w.get("x", w.get("col", 0))
                y = w.get("y", w.get("row", 0))
                w_cells = w.get("w", w.get("colspan", 1))
                h_cells = w.get("h", w.get("rowspan", 1))
                try:
                    xi = int(x); yi = int(y); wi = max(1, int(w_cells)); hi = max(1, int(h_cells))
                except Exception:
                    continue
                norm.append({"id": w.get("id") or ent or f"idx:{len(norm)}", "x": xi, "y": yi, "w": wi, "h": hi})
            for i in range(len(norm)):
                a = norm[i]; ax2 = a["x"] + a["w"]; ay2 = a["y"] + a["h"]
                for j in range(i+1, len(norm)):
                    b = norm[j]; bx2 = b["x"] + b["w"]; by2 = b["y"] + b["h"]
                    if not (ax2 <= b["x"] or bx2 <= a["x"] or ay2 <= b["y"] or by2 <= a["y"]):
                        overlaps.append(f"{a['id']} ↔ {b['id']}")
        except Exception:
            logging.getLogger(__name__).exception("profiles_device: overlap detection failed for %s", dev_id)

        if overlaps:
            warn = "OVERLAPPING WIDGETS: " + ", ".join(overlaps) + ". Adjust positions so each (x,y,w,h) region is unique."
            _LOGGER.warning("profiles_device: overlaps detected for %s -> %s", dev_id, overlaps)
            restored_txt = txt if isinstance(txt, str) else json.dumps(parsed, indent=2, ensure_ascii=False)
            return self.async_show_form(
                step_id="profiles_device",
                errors={"base": "overlaps"},
                data_schema=_schema_with_defaults(dev_id, restored_txt),
                description_placeholders={"desc": warn + "\n\nFix overlaps and submit again."},
            )
        # Merge into latest Store snapshot before persisting
        base_profiles = {}
        try:
            helper = StorageHelper(self.hass, self._entry)
            await helper.async_init()
            base_profiles = dict(helper.storage.get(CONF_PROFILES) or {})
        except Exception:
            logging.getLogger(__name__).exception("profiles_device: failed to reload Store before save")
        base_profiles[prof_name] = parsed
        self._profiles = base_profiles
        self._data[CONF_PROFILES] = self._profiles

        devs = list(self._data.get(CONF_DEVICES, []) or [])
        if not any((d.get("device_id") == dev_id) for d in devs):
            devs.append({"device_id": dev_id, "profile": dev_id})
        else:
            for d in devs:
                if d.get("device_id") == dev_id:
                    d["profile"] = dev_id
        # If an old assigned profile name existed for this device and is different, remove it if unused elsewhere
        prev_assigned = None
        for d in (self._devices or []):
            if d.get("device_id") == dev_id:
                prev_assigned = d.get("profile")
                break
        # Determine profiles referenced by any device to avoid deleting shared ones
        referenced: set[str] = set()
        for d in devs:
            if d.get("profile"):
                referenced.add(d.get("profile"))
            if d.get("device_id"):
                referenced.add(d.get("device_id"))
        # Prune obvious stray keys like 'main_panel' or previous assigned key if unreferenced
        to_prune: list[str] = []
        if prev_assigned and prev_assigned != dev_id and prev_assigned in self._profiles and prev_assigned not in referenced:
            to_prune.append(prev_assigned)
        if "main_panel" in self._profiles and "main_panel" not in referenced:
            to_prune.append("main_panel")
        for k in to_prune:
            try:
                self._profiles.pop(k, None)
                logging.getLogger(__name__).debug("profiles_device: pruned stray profile key '%s'", k)
            except Exception:
                pass
        self._data[CONF_PROFILES] = self._profiles
        self._data[CONF_DEVICES] = devs
        _LOGGER.debug(
            "profiles_device: saved device=%s profile_key=%s decision=%s profiles_count=%d devices_count=%d",
            dev_id, prof_name, locals().get("decided", "unknown"), len(self._profiles or {}), len(devs),
        )
        if not overlaps:
            _LOGGER.debug("profiles_device: no overlaps for device=%s (widgets=%d)", dev_id, len(norm))
        # Persist directly to HA Store so edits survive reloads regardless of options listener timing
        try:
            helper = StorageHelper(self.hass, self._entry)
            # Load existing store (defensive) then persist merged profiles (mirrors to options)
            await helper.async_init()
            await helper.persist_profiles(dict(self._profiles))
            _LOGGER.debug("profiles_device: persisted profiles to Store (keys=%s)", list(self._profiles.keys()))
        except Exception:
            _LOGGER.exception("profiles_device: failed to persist profiles to Store for %s", dev_id)
        # Immediately publish updated config & reload device so UI refreshes without manual button
        try:
            bridge = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.entry_id in self.hass.data.get(DOMAIN, {}):
                    bridge = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if bridge:
                bridge.schedule_republish_reload("profile_save")
                _LOGGER.debug("profiles_device: scheduled debounced publish+reload for %s", dev_id)
        except Exception:
            _LOGGER.exception("profiles_device: scheduling publish+reload failed for %s", dev_id)
        return self.async_create_entry(title="", data=self._data)

    # Devices: add device
    async def async_step_devices_add(self, user_input=None):
        if user_input is None:
            schema = vol.Schema({ vol.Required("device_id"): str })
            return self.async_show_form(step_id="devices_add", data_schema=schema)
        dev_id = (user_input.get("device_id") or "").strip()
        if not dev_id:
            return self.async_abort(reason="invalid_device_id")
        # Ensure device exists and has a profile key
        devs = list(self._devices)
        if not any(d.get("device_id") == dev_id for d in devs):
            devs.append({"device_id": dev_id, "profile": dev_id})
        self._data[CONF_DEVICES] = devs
        if dev_id not in (self._profiles or {}):
            self._profiles[dev_id] = {"grid": {"columns": 4}, "widgets": []}
            self._data[CONF_PROFILES] = self._profiles
        # Schedule republish+reload so the device gets a retained config immediately
        try:
            bridge = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.entry_id in self.hass.data.get(DOMAIN, {}):
                    bridge = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if bridge:
                bridge.schedule_republish_reload("devices_add")
        except Exception:
            logging.getLogger(__name__).exception("devices_add: could not schedule republish")
        return self.async_create_entry(title="", data=self._data)

    def _device_profile(self, device_id: str) -> str:
        for d in self._devices:
            if d.get("device_id") == device_id:
                return d.get("profile", "")
        return ""

    # Remove devices_assign step entirely (device profiles are locked to device_id)

    # Mirror picker
    async def async_step_mirror(self, user_input=None):
        schema = vol.Schema({
            vol.Optional(CONF_MIRROR_ENTITIES, default=self._mirror_entities): selector.EntitySelector(
                selector.EntitySelectorConfig(multiple=True)
            ),
        })
        if user_input is None:
            logging.getLogger(__name__).debug("options_flow:mirror form presented")
            return self.async_show_form(step_id="mirror", data_schema=schema)
        ents = list(user_input.get(CONF_MIRROR_ENTITIES, []) or [])
        logging.getLogger(__name__).debug("options_flow:mirror saving count=%d", len(ents))
        # Strip legacy keys from options payload on save
        self._data.pop("mirror_enabled", None)
        self._data.pop("mirror_attributes", None)
        self._data[CONF_MIRROR_ENTITIES] = ents
        return self.async_create_entry(title="", data=self._data)

    # (Topics step removed; all base topics fixed to mqttdash/*)

    # Advanced step removed: republishing occurs automatically on save, and device removal uses HA's Delete Device
    # Quick guide
    async def async_step_guide(self, user_input=None):
        logging.getLogger(__name__).debug("options_flow:guide opened")
        tips = []
        host = "homeassistant.local"
        hass_ip = getattr(self.hass.config, "api", None) and self.hass.config.api.host or ""
        tips.append(f"Broker host: {host} (or {hass_ip})")
        tips.append("Port: 1883 (no TLS)")
        tips.append("Create MQTT user/pass in Mosquitto add-on and assign to the app.")
        tips.append("Retained config: mqttdash/config/<device_id>/config")
        tips.append("Device settings: mqttdash/dev/<device_id>/settings")
        tips.append("Device hello: mqttdash/dev/<device_id>/hello")
        tips.append("Device status LWT: mqttdash/dev/<device_id>/status")
        tips.append("Entity commands: mqttdash/cmd/<entity_id>")
        tips.append("Mirrored states: mqttdash/statestream/<domain>/<object>/state")

        schema = vol.Schema({vol.Optional("publish_test", default=False): bool})
        if user_input is None:
            return self.async_show_form(step_id="guide", data_schema=schema,
                                        description_placeholders={"text": "\n".join(tips)})

        if user_input.get("publish_test"):
            from homeassistant.components import mqtt # type: ignore
            logging.getLogger(__name__).debug("options_flow:guide publishing test hello")
            await mqtt.async_publish(self.hass, "mqttdash/dev/test/hello", '{"hello":true}', qos=0, retain=False)
        return self.async_create_entry(title="", data=self._data)
