from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set
from homeassistant.helpers.storage import Store  # type: ignore
from homeassistant.core import HomeAssistant, Event  # type: ignore
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED  # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.components import mqtt  # type: ignore
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNKNOWN, STATE_UNAVAILABLE  # type: ignore
from homeassistant.helpers.event import async_track_state_change_event  # type: ignore
from homeassistant.helpers.event import async_track_time_interval  # type: ignore
from homeassistant.helpers.event import async_call_later  # type: ignore
from datetime import timedelta
from homeassistant.helpers.dispatcher import async_dispatcher_send  # type: ignore
from homeassistant.helpers import device_registry as dr  # type: ignore
from homeassistant.helpers import entity_registry as er  # type: ignore
from .const import (
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_MIRROR_ENTITIES,
    DOMAIN,
    SIGNAL_DEVICE_SETTINGS_UPDATED,
    FIXED_CONFIG_BASE, FIXED_DEVICE_BASE, FIXED_COMMAND_BASE, FIXED_STATESTREAM_BASE,
)
from .storage import StorageHelper

# Fixed mqttdash namespace (replaces legacy 'ha/*' topics). User configuration of bases removed.
_LOGGER = logging.getLogger(__name__)

def _payload_to_str(msg) -> str:
    """Return payload as text, whether it's bytes, str, or None."""
    try:
        p = msg.payload
    except AttributeError:
        # Defensive: if someone passed the raw payload instead of ReceiveMessage
        p = msg
    if p is None:
        return ""
    if isinstance(p, bytes):
        try:
            return p.decode("utf-8", "ignore")
        except Exception:
            return ""
    # HA often gives str already
    return str(p)

class MqttBridge:
    """Bridge HA <-> iOS dashboard via MQTT."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        # Raw persisted config entry data/options snapshots
        self._data: Dict[str, Any] = dict(entry.data or {})
        self._opts: Dict[str, Any] = dict(entry.options or {})
        # Public merged view used during runtime
        self.cfg: Dict[str, Any] = {**self._data, **self._opts}

        # Debounce delay for republish+reload operations (short for responsive UI saves)
        self._debounce_seconds: float = 0.25

        # Subscription handles / timers
        self._unsubs: List[Any] = []
        self._mirror_unsub: Optional[Any] = None

        # Mirror tracking
        self._last_mirror_set = set(self.cfg.get(CONF_MIRROR_ENTITIES, []) or [])
        # Track last-published state and attributes per entity for proper retained dedupe/purge
        # _last_state["domain.object"] = "last_state_str"
        self._last_state = {}
        # _attr_vals_by_entity["domain.object"] = { key: "str(value)", ... }
        self._attr_vals_by_entity = {}

        # Track prior device id set to detect removals (for retained purge)
        self._last_device_ids = set(
            [d.get("device_id") for d in self.cfg.get(CONF_DEVICES, []) or [] if d.get("device_id")]
        )

        # Telemetry cache (per device)
        self._telemetry = {}

        # Debounce bookkeeping
        self._republish_reload_handle = None
        self._republish_reload_pending = False
        self._last_republish_reload_sec = 0.0
        # Debounced entry reload to make new/renamed devices appear immediately
        self._entry_reload_handle = None
        self._entry_reload_debounce_seconds: float = 0.25
        # HA Store helper for persistent data (profiles, device_settings)
        self._storage_helper = StorageHelper(self.hass, self.entry)
        self._storage = {"profiles": {}, "device_settings": {}}
        self._in_options_migration = False
        self._setup_complete = False

    def schedule_republish_reload(self, reason: str = "") -> None:
        """Debounce multiple rapid requests to republish configs & reload all devices."""
        import time
        self._republish_reload_pending = True
        # If a timer already scheduled, let it fire
        if self._republish_reload_handle is not None:
            _LOGGER.debug("schedule_republish_reload: already scheduled (%s)", reason)
            return
        # We intentionally avoid publishing immediately to ensure the client sees the reload first,
        # then receives a fresh config publish afterwards.
        async def _fire(_now):
            await self._do_republish_reload(reason)
        self._republish_reload_handle = async_call_later(self.hass, self._debounce_seconds, _fire)
        _LOGGER.debug("schedule_republish_reload: scheduled in %.2fs (%s)", self._debounce_seconds, reason)

    async def _do_republish_reload(self, reason: str = "") -> None:
        import time
        self._republish_reload_handle = None
        if not self._republish_reload_pending:
            return
        self._republish_reload_pending = False
        try:
            # Refresh runtime config from latest entry and Store just before publishing
            try:
                # Reload HA Store to pick up any external writes (e.g., from options flow or services)
                try:
                    self._in_options_migration = True  # suppress listener reactions to mirror writes
                    await self._storage_helper.async_init()
                    self._storage = dict(self._storage_helper.storage)
                finally:
                    self._in_options_migration = False
                latest_data = dict(self.entry.data or {})
                latest_opts = dict(self.entry.options or {})
                # Always source profiles from Store (canonical)
                store_profs = dict(self._storage_helper.storage.get("profiles") or {})
                latest_opts[CONF_PROFILES] = store_profs
                self._data = latest_data
                self._opts = latest_opts
                self.cfg = {**self._data, **self._opts}
                _LOGGER.debug(
                    "republish_reload: refreshed cfg before publish (devices=%d profiles=%d)",
                    len(self.cfg.get(CONF_DEVICES, []) or []),
                    len((self.cfg.get(CONF_PROFILES, {}) or {}).keys()),
                )
            except Exception:
                _LOGGER.exception("republish_reload: cfg refresh failed")
            devices: List[Dict[str, Any]] = list(self.cfg.get(CONF_DEVICES, []) or [])
                # First: send reload to devices (non-retained) so they clear and expect a new config
            for d in devices:
                did = (d.get("device_id") or "").strip()
                if did:
                    await self.async_publish_device_action(did, action="reload")
            # Then: publish updated configs so subscribers receive the new retained payloads
            await self.async_publish_all_configs()
            self._last_republish_reload_sec = time.time()
            _LOGGER.debug("republish_reload: completed for %d device(s) (%s)", len(devices), reason)
        except Exception:
            _LOGGER.exception("republish_reload: failure (%s)", reason)

    def schedule_entry_reload(self, reason: str = "") -> None:
        """Debounce and reload the config entry to update HA devices/entities immediately."""
        if self._entry_reload_handle is not None:
            _LOGGER.debug("schedule_entry_reload: already scheduled (%s)", reason)
            return
        async def _fire(_now):
            self._entry_reload_handle = None
            try:
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                _LOGGER.debug("entry reloaded (%s)", reason)
            except Exception:
                _LOGGER.exception("entry reload failed (%s)", reason)
        self._entry_reload_handle = async_call_later(self.hass, self._entry_reload_debounce_seconds, _fire)
        _LOGGER.debug("schedule_entry_reload: scheduled in %.2fs (%s)", self._entry_reload_debounce_seconds, reason)

    # ---------- lifecycle ----------
    async def async_setup(self) -> None:
        _LOGGER.debug("mqtt_bridge.setup: subscribing fixed bases cmd=%s dev=%s", FIXED_COMMAND_BASE, FIXED_DEVICE_BASE)
        self._unsubs.append(await mqtt.async_subscribe(self.hass, f"{FIXED_COMMAND_BASE}/#", self._on_cmd))
        self._unsubs.append(await mqtt.async_subscribe(self.hass, f"{FIXED_DEVICE_BASE}/+/request", self._on_device_request))
        self._unsubs.append(await mqtt.async_subscribe(self.hass, f"{FIXED_DEVICE_BASE}/+/hello", self._on_device_hello))
        self._unsubs.append(await mqtt.async_subscribe(self.hass, f"{FIXED_DEVICE_BASE}/+/telemetry/#", self._on_device_telemetry))
        # Initialize HA storage and migrate legacy options before first publish
        try:
            # Suppress options-updated reactions while Store mirrors to options during init
            self._in_options_migration = True
            await self._storage_helper.async_init()
            self._storage = dict(self._storage_helper.storage)
            # If Store has no profiles but the entry has initial profiles (e.g., from onboarding), seed the Store
            try:
                profs_store = dict(self._storage.get("profiles") or {})
                if not profs_store:
                    initial_profiles = {}
                    try:
                        initial_profiles = dict((self.entry.data or {}).get(CONF_PROFILES) or {})
                        if not initial_profiles:
                            initial_profiles = dict((self.entry.options or {}).get(CONF_PROFILES) or {})
                    except Exception:
                        initial_profiles = {}
                    if initial_profiles:
                        _LOGGER.debug("mqtt_bridge.setup: seeding Store with initial profiles from entry (%d)", len(initial_profiles))
                        await self._storage_helper.persist_profiles(initial_profiles)
                        self._storage = dict(self._storage_helper.storage)
            except Exception:
                _LOGGER.exception("mqtt_bridge.setup: failed to seed Store from entry profiles")
            # After storage init, ensure runtime cfg reflects canonical Store profiles
            try:
                profs_store = dict(self._storage.get("profiles") or {})
                self._opts = dict(self.entry.options or {})
                # Always override profiles with Store copy for runtime
                self._opts[CONF_PROFILES] = profs_store
                _LOGGER.debug("mqtt_bridge.setup: using Store profiles for runtime (%d)", len(profs_store))
                self._data = dict(self.entry.data or {})
                self.cfg = {**self._data, **self._opts}
                _LOGGER.debug(
                    "mqtt_bridge.setup: runtime cfg ready (devices=%d profiles=%d)",
                    len(self.cfg.get(CONF_DEVICES, []) or []),
                    len((self.cfg.get(CONF_PROFILES, {}) or {}).keys()),
                )
            except Exception:
                _LOGGER.exception("post-storage init cfg merge failed")
        except Exception:
            _LOGGER.exception("init storage failed")
        await self.async_publish_all_configs()
        # Subscribe to mirror without snapshot yet; we'll publish a single snapshot on HA started
        await self._maybe_start_mirror(publish_snapshot=False)
        # Re-enable options update handling after initial publish
        self._in_options_migration = False
        self._setup_complete = True
        # After HA startup, publish a full snapshot to ensure devices get initial states
        async def _on_started(_event):
            try:
                _LOGGER.debug("mqtt_bridge: HA started -> refreshing Store and publishing configs")
                # Reload Store to ensure final state after startup
                try:
                    await self._storage_helper.async_init()
                    self._storage = dict(self._storage_helper.storage)
                except Exception:
                    _LOGGER.exception("startup: storage re-init failed")
                # Rebuild runtime cfg strictly from Store and publish configs
                try:
                    profs_store = dict(self._storage.get("profiles") or {})
                    self._opts = dict(self.entry.options or {})
                    self._opts[CONF_PROFILES] = profs_store
                    self._data = dict(self.entry.data or {})
                    self.cfg = {**self._data, **self._opts}
                    _LOGGER.debug(
                        "startup: runtime cfg built from Store (devices=%d profiles=%d)",
                        len(self.cfg.get(CONF_DEVICES, []) or []),
                        len((self.cfg.get(CONF_PROFILES, {}) or {}).keys()),
                    )
                except Exception:
                    _LOGGER.exception("startup: cfg rebuild failed")
                await self.async_publish_all_configs()
                # Start/restart mirror and publish initial snapshot
                await self._maybe_start_mirror()
                await self.async_publish_snapshot()
            except Exception:
                _LOGGER.exception("startup: initial publish failed")
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

        # Removed periodic device pings to reduce CPU/network churn. Devices publish telemetry
        # on change and on connect; snapshots remain on-demand or at startup.

    async def async_dump_store(self, publish: bool = False, topic: Optional[str] = None) -> None:
        """Log current HA Store contents (profiles and device_settings).
        If publish is True, also publish the JSON to an MQTT topic.
        """
        try:
            data = dict(self._storage_helper.storage or {})
        except Exception:
            data = {"profiles": {}, "device_settings": {}}
        profiles = data.get("profiles") or {}
        dev_settings = data.get("device_settings") or {}
        pkeys = list(profiles.keys()) if isinstance(profiles, dict) else []
        dkeys = list(dev_settings.keys()) if isinstance(dev_settings, dict) else []
        _LOGGER.info(
            "dump_store: profiles=%d keys=%s device_settings=%d device_ids=%s",
            (len(pkeys) if isinstance(pkeys, list) else 0), pkeys, (len(dkeys) if isinstance(dkeys, list) else 0), dkeys,
        )
        # Pretty JSON (truncate in logs); full content if publishing
        try:
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            pretty = str(data)
        max_log = 20000
        if len(pretty) > max_log:
            _LOGGER.info("dump_store (truncated): %s... (%d bytes)", pretty[:max_log], len(pretty))
        else:
            _LOGGER.info("dump_store: %s", pretty)
        if publish:
            try:
                t = topic or f"mqttdash/debug/{self.entry.entry_id}/store_dump"
                await mqtt.async_publish(self.hass, t, pretty, qos=0, retain=False)
                _LOGGER.info("dump_store: published to %s", t)
            except Exception:
                _LOGGER.exception("dump_store: publish failed")

    async def async_dump_runtime_cfg(self, publish: bool = False, topic: Optional[str] = None) -> None:
        """Log current merged runtime configuration (self.cfg). Optionally publish as JSON."""
        try:
            cfg_now = dict(self.cfg or {})
        except Exception:
            cfg_now = {}
        # Summaries
        try:
            devices = list(cfg_now.get(CONF_DEVICES, []) or [])
            profiles = dict(cfg_now.get(CONF_PROFILES, {}) or {})
            _LOGGER.info(
                "dump_runtime_cfg: devices=%d profiles=%d keys=%s",
                len(devices), len(profiles), list(profiles.keys()),
            )
        except Exception:
            pass
        try:
            pretty = json.dumps(cfg_now, indent=2, ensure_ascii=False)
        except Exception:
            pretty = str(cfg_now)
        max_log = 20000
        if len(pretty) > max_log:
            _LOGGER.info("dump_runtime_cfg (truncated): %s... (%d bytes)", pretty[:max_log], len(pretty))
        else:
            _LOGGER.info("dump_runtime_cfg: %s", pretty)
        if publish:
            try:
                t = topic or f"mqttdash/debug/{self.entry.entry_id}/runtime_cfg"
                await mqtt.async_publish(self.hass, t, pretty, qos=0, retain=False)
                _LOGGER.info("dump_runtime_cfg: published to %s", t)
            except Exception:
                _LOGGER.exception("dump_runtime_cfg: publish failed")

    async def async_send_notification(self, device_id: str, message: str, title: Optional[str] = None) -> None:
        """Publish a notification to the device's notify topic."""
        try:
            if not isinstance(device_id, str) or not device_id.strip():
                _LOGGER.warning("notify: missing device_id")
                return
            if not isinstance(message, str) or not message.strip():
                _LOGGER.warning("notify: missing message")
                return
            payload = {"message": message}
            if isinstance(title, str) and title.strip():
                payload["title"] = title.strip()
            topic = f"{FIXED_DEVICE_BASE}/{device_id}/notify"
            await mqtt.async_publish(self.hass, topic, json.dumps(payload), qos=0, retain=False)
            _LOGGER.debug("notify: published to %s", topic)
        except Exception:
            _LOGGER.exception("notify: failed for %s", device_id)

    def get_device_settings(self, device_id: str) -> Dict[str, Any]:
        try:
            return self._storage_helper.get_device_settings(device_id)
        except Exception:
            return {}

    async def _init_storage(self) -> None:
        # Deprecated: logic moved to StorageHelper. Kept to avoid breaking calls; no-op.
        return

    async def async_unload(self) -> None:
        for u in self._unsubs:
            try: u()
            except Exception: pass
        self._unsubs.clear()
        if self._mirror_unsub:
            try: self._mirror_unsub()
            except Exception: pass
            self._mirror_unsub = None

    async def async_options_updated(self, updated_entry: ConfigEntry) -> None:
        # Avoid re-entrant loops when we update options internally to mirror Store
        if getattr(self, "_in_options_migration", False):
            self._in_options_migration = False
            _LOGGER.debug("options_updated: skipping due to internal migration")
            return
        self.entry = updated_entry
        # Always merge data+options; never drop existing profiles/devices on partial updates
        self._data = dict(updated_entry.data or {})
        self._opts = dict(updated_entry.options or {})
        # Persist incoming profiles (if any) to Store; runtime will always use Store thereafter
        try:
            incoming_profiles = self._opts.get(CONF_PROFILES)
            if isinstance(incoming_profiles, dict):
                await self._storage_helper.persist_profiles(dict(incoming_profiles))
                self._storage = dict(self._storage_helper.storage)
        except Exception:
            _LOGGER.exception("options_updated: persist to store failed")
        # Force runtime profiles to Store copy
        try:
            store_profs = dict(self._storage_helper.storage.get("profiles") or {})
            self._opts[CONF_PROFILES] = store_profs
        except Exception:
            _LOGGER.exception("options_updated: load store profiles failed")
        self.cfg = {**self._data, **self._opts}
        _LOGGER.debug(
            "options_updated: merged keys data=%s options=%s",
            list((updated_entry.data or {}).keys()), list((updated_entry.options or {}).keys()),
        )
        _LOGGER.debug(
            "mqtt_bridge.options_updated: devices=%d profiles=%d mirror=%d",
            len(self.cfg.get(CONF_DEVICES, []) or []),
            len((self.cfg.get(CONF_PROFILES, {}) or {}).keys()),
            len(self.cfg.get(CONF_MIRROR_ENTITIES, []) or []),
        )

        new_mirror = set(self.cfg.get(CONF_MIRROR_ENTITIES, []) or [])
        removed_mirror = self._last_mirror_set - new_mirror
        added_mirror = new_mirror - self._last_mirror_set
        if removed_mirror:
            await self._purge_mirror_entities(removed_mirror)
        self._last_mirror_set = new_mirror

        # Purge configs for devices removed from options
        current_ids: Set[str] = set([d.get("device_id") for d in self.cfg.get(CONF_DEVICES, []) or [] if d.get("device_id")])
        removed_devices = self._last_device_ids - current_ids
        added_devices = current_ids - self._last_device_ids
        # Respect user option for placeholder behavior; default False to avoid ghosts
        placeholder_flag = bool(self.entry.options.get("placeholder_on_remove", False))
        for did in removed_devices:
            await self._purge_device_retained(did, placeholder=placeholder_flag)
        # If device set changed, reload entry so entities/devices appear/disappear immediately
        if self._setup_complete and (removed_devices or added_devices):
            self.schedule_entry_reload("options_devices_changed")
        self._last_device_ids = current_ids

        # Cleanup unused profiles to avoid stale/unreferenced keys lingering
        try:
            # Use helper to prune unused profiles in Store and mirror to options
            profs = dict(self._storage_helper.storage.get("profiles") or {})
            devs = list(self.cfg.get(CONF_DEVICES, []) or [])
            remaining = await self._storage_helper.prune_unused_profiles(profs, devs)
            # Update local caches
            self._storage = dict(self._storage_helper.storage)
            # Mirror newest Store profiles back to options for UI, without triggering loops
            try:
                self._in_options_migration = True
                new_opts = {**(self.entry.options or {})}
                new_opts[CONF_PROFILES] = dict(remaining)
                self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
                self._opts = dict(new_opts)
                self._opts[CONF_PROFILES] = dict(remaining)
                self.cfg = {**self._data, **self._opts}
            except Exception:
                _LOGGER.exception("mirror to options failed")
        except Exception:
            _LOGGER.exception("profile prune failed")
        # Always republish configs on any options change (profiles, devices, topics)
        _LOGGER.debug("mqtt_bridge.options_updated: triggering republish+reload")
        # Mirror subscriptions may have changed
        await self._maybe_start_mirror(publish_snapshot=False)
        # Profiles already persisted above (if provided); ensure runtime uses Store copy
        # Trigger immediate republish using the refreshed cfg
        self._republish_reload_pending = True
        await self._do_republish_reload("options_updated")

    # ---------- retained config ----------
    async def async_publish_all_configs(self) -> None:
        # Use latest merged in-memory config (self.cfg) so we include any disk-loaded profiles
        # even before ConfigEntry.options round-trips through HA.
        cfg_now: Dict[str, Any] = dict(self.cfg or {})
        base_cfg = FIXED_CONFIG_BASE
        devices: List[Dict[str, Any]] = list(cfg_now.get(CONF_DEVICES, []) or [])
        _LOGGER.debug("publishing configs: %d device(s) to fixed base %s", len(devices), base_cfg)
        for dev in devices:
            device_id = (dev.get("device_id") or "").strip()
            if not device_id:
                continue
            doc = self._build_config_for_device(dev, cfg_now)
            try:
                payload = json.dumps(doc, separators=(",", ":"))
            except Exception as ex:
                _LOGGER.warning("config JSON encode failed for %s: %s", device_id, ex)
                continue
            try:
                import hashlib
                phash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            except Exception:
                phash = ""
            topic = f"{base_cfg}/{device_id}/config"
            _LOGGER.debug("mqtt_bridge.publish_config: %s bytes=%d hash=%s", topic, len(payload), phash[:12])
            await mqtt.async_publish(self.hass, f"{base_cfg}/{device_id}/config", payload, qos=0, retain=True)

    async def async_dump_device_config(self, device_id: str, publish: bool = False, topic: Optional[str] = None) -> None:
        """Build and log the exact config JSON for a single device; optionally publish it."""
        try:
            cfg_now: Dict[str, Any] = dict(self.cfg or {})
            devs: List[Dict[str, Any]] = list(cfg_now.get(CONF_DEVICES, []) or [])
            dev = next((d for d in devs if (d.get("device_id") or "").strip() == device_id.strip()), None)
            if not dev:
                _LOGGER.warning("dump_device_config: device %s not found in devices list", device_id)
                return
            doc = self._build_config_for_device(dev, cfg_now)
            pretty = json.dumps(doc, indent=2, ensure_ascii=False)
            _LOGGER.info("dump_device_config(%s): %s", device_id, pretty)
            if publish:
                t = topic or f"mqttdash/debug/{device_id}/config"
                await mqtt.async_publish(self.hass, t, pretty, qos=0, retain=False)
                _LOGGER.info("dump_device_config: published to %s", t)
        except Exception:
            _LOGGER.exception("dump_device_config failed for %s", device_id)

    def _build_config_for_device(self, dev: Dict[str, Any], cfg_now: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        device_id = dev.get("device_id") or ""
        profile_name = dev.get("profile") or ""
        src_cfg = cfg_now if cfg_now is not None else self.cfg
        profiles: Dict[str, Any] = dict(src_cfg.get(CONF_PROFILES, {}) or {})
        # Device-specific profiles: prefer profile keyed by device_id
        prof = profiles.get(device_id)
        if not prof and profile_name:
            prof = profiles.get(profile_name)
        try:
            _LOGGER.debug(
                "build_config: device=%s profile_key=%s found=%s", device_id, profile_name or device_id, bool(prof)
            )
        except Exception:
            pass
        # Harden: if no profile assigned but exactly one profile exists, auto-assign it
        if not prof and len(profiles) == 1:
            try:
                only_name, only_prof = next(iter(profiles.items()))
                prof = only_prof
                _LOGGER.debug("auto-assigning lone profile '%s' to %s", only_name, device_id)
            except Exception:
                pass
        # Or use a profile named "default" if present
        if not prof and "default" in profiles:
            prof = profiles.get("default")
        base_dev = FIXED_DEVICE_BASE

        if not prof:
            _LOGGER.debug("build_config: no profile -> publishing unassigned placeholder for %s", device_id)
            return {
                "device_id": device_id,
                # Device settings are not part of profile config anymore; app receives only UI + topics
                "ui": { "widgets": [], "banner": f"unassigned: set profile in HA for {device_id}" },
                "topics": {
                    "settings": f"{base_dev}/{device_id}/settings",
                    "hello":    f"{base_dev}/{device_id}/hello",
                    "status":   f"{base_dev}/{device_id}/status",
                },
            }

        # Normalize profile -> app config schema expected by iOS client
        # App expects: { device_id, device:{...}, ui:{ widgets:[], grid?, ... }, topics:{...} }
        raw = dict(prof)
        # If profile is wrapped in a single top-level key (e.g., {"main_panel": {...}}), unwrap it
        try:
            if isinstance(raw, dict) and len(raw.keys()) == 1:
                only_key = next(iter(raw.keys()))
                inner = raw.get(only_key)
                # Heuristic: if inner looks like a profile body, unwrap
                if isinstance(inner, dict) and ("widgets" in inner or "ui" in inner or "grid" in inner or "dashboard" in inner):
                    _LOGGER.debug("build_config: unwrapping single-key profile '%s' for device=%s", only_key, device_id)
                    raw = dict(inner)
        except Exception:
            pass

        # Device settings are moved to HA entities; config now contains only UI and topics
        device = {}

        # Build UI bucket and move widgets/grid-like keys under ui
        ui: Dict[str, Any] = {}
        if isinstance(raw.get("ui"), dict):
            ui = dict(raw.get("ui") or {})
        # Move known layout keys from top-level if present
        for k in ("grid", "rowHeight", "gutter", "padding", "cols", "rows"):
            if k in raw and k not in ui:
                ui[k] = raw.pop(k)
        # Widgets can be top-level or inside ui; normalize to ui.widgets
        widgets = None
        if isinstance(raw.get("widgets"), list):
            widgets = list(raw.get("widgets") or [])
        elif isinstance(ui.get("widgets"), list):
            widgets = list(ui.get("widgets") or [])
        else:
            widgets = []
        try:
            _LOGGER.debug("build_config: device=%s initial_widgets=%d (pre-layout)", device_id, len(widgets or []))
        except Exception:
            pass

        # HADashboard-like layout support (starter):
        # If profile defines grid columns and a layout array of rows with entries like
        #   "light.kitchen", "sensor.temp", "light.living(2x1)", "spacer", ""
        # we translate them into concrete widget defs with x,y,w,h and topics.
        try:
            dash = raw.get("dashboard") if isinstance(raw.get("dashboard"), dict) else raw
            cols = None
            layout = None
            dash_src = dash if isinstance(dash, dict) else {}
            if isinstance(dash_src, dict):
                cols = dash_src.get("columns") or dash_src.get("cols") or ui.get("columns")
                layout = dash_src.get("layout") or ui.get("layout")
            if isinstance(cols, int) and cols > 0 and isinstance(layout, list):
                # Adopt widget_dimensions and margins if present
                wd = dash_src.get("widget_dimensions") or ui.get("widget_dimensions") or [120, 120]
                wm = dash_src.get("widget_margins") or ui.get("widget_margins") or [5, 5]
                ws = dash_src.get("widget_size") or ui.get("widget_size") or [1, 1]
                ui["grid"] = {
                    "columns": cols,
                    "widget_dimensions": wd,
                    "widget_margins": wm,
                    "widget_size": ws,
                }
                base_stream = FIXED_STATESTREAM_BASE
                base_cmd = FIXED_COMMAND_BASE

                def _parse_size(s: str):
                    # looks for "(WxH)"
                    if not isinstance(s, str):
                        return (ws[0], ws[1])
                    i = s.find("(")
                    j = s.find(")", i+1) if i >= 0 else -1
                    if i >= 0 and j > i:
                        try:
                            inner = s[i+1:j]
                            if "x" in inner:
                                a, b = inner.split("x", 1)
                                return (int(a), int(b))
                        except Exception:
                            return (ws[0], ws[1])
                    return (ws[0], ws[1])

                def _strip_size(s: str):
                    if not isinstance(s, str):
                        return s
                    i = s.find("(")
                    return s[:i].strip() if i > 0 else s.strip()

                def _mk_widget(entity: str, x: int, y: int, w: int, h: int) -> Optional[Dict[str, Any]]:
                    if not entity:
                        return None
                    ent = entity.strip()
                    if ent.lower() in ("spacer",):
                        return None
                    if "." not in ent and ent.lower() not in ("clock", "weather"):
                        # Skip unknown non-entity widgets for now
                        return None
                    label = ent
                    cmd_topic = None
                    state_topic = None
                    wtype = "value"
                    dom = None
                    obj = None
                    if "." in ent:
                        dom, obj = ent.split(".", 1)
                        state_topic = f"{base_stream}/{dom}/{obj}/state"
                        if dom == "light":
                            wtype = "light"
                            cmd_topic = f"{base_cmd}/{ent}"
                        elif dom in ("switch", "input_boolean"):
                            wtype = "switch"
                            cmd_topic = f"{base_cmd}/{ent}"
                        elif dom == "scene":
                            wtype = "scene"
                            cmd_topic = f"{base_cmd}/{ent}"
                        elif dom in ("script", "button"):
                            wtype = "button"
                            cmd_topic = f"{base_cmd}/{ent}"
                        else:
                            wtype = "sensor"
                    else:
                        # non-entity simple widgets placeholder -> sensor-like for now
                        wtype = "sensor"
                    wdict = {
                        "id": f"g:{x},{y}:{ent}",
                        "type": wtype,
                        "entity_id": ent if "." in ent else "",
                        "state_topic": state_topic or "",
                        "command_topic": cmd_topic or None,
                        "label": label,
                        "x": x, "y": y, "w": w, "h": h,
                    }
                    # Provide attr_topic for brightness on lights to support UI brightness controls
                    if dom == "light" and obj:
                        wdict["attr_topic"] = f"{base_stream}/{dom}/{obj}/attributes/brightness"
                    return wdict

                widgets_from_layout: List[Dict[str, Any]] = []
                y = 0
                for row in layout:
                    # each row can be a string with comma separated entries or an array
                    if isinstance(row, str):
                        parts = [p.strip() for p in row.split(",")]
                    elif isinstance(row, list):
                        parts = row
                    elif isinstance(row, dict) and "empty" in row:
                        try:
                            nraw = row.get("empty")
                            nempty = int(nraw) if nraw is not None else 1
                        except Exception:
                            nempty = 1
                        y += max(0, nempty)
                        continue
                    else:
                        y += 1
                        continue

                    x = 0
                    for item in parts:
                        if not item or item.lower() == "spacer":
                            x += 1
                            continue
                        w_cells, h_cells = _parse_size(item)
                        name = _strip_size(item)
                        wdef = _mk_widget(name, x, y, w_cells, h_cells)
                        if wdef:
                            widgets_from_layout.append(wdef)
                        x += max(1, int(w_cells))
                    y += 1

                # Merge: explicit widgets (if any) first, then append layout-generated
                widgets.extend(widgets_from_layout)
        except Exception:
            _LOGGER.exception("Failed to parse dashboard layout")

        # At this point, widgets may contain raw profile-defined dicts. Profiles should NOT
        # include MQTT topics; generate them here based on entity_id and type. Also accept
        # user-friendly aliases for coordinates: row/col/rowspan/colspan.
        norm_widgets: List[Dict[str, Any]] = []
        base_stream = FIXED_STATESTREAM_BASE
        base_cmd = FIXED_COMMAND_BASE

        def _coerce_int(v: Any, default: int) -> int:
            try:
                if isinstance(v, bool):
                    return default
                return int(v)
            except Exception:
                return default

        for idx, it in enumerate(widgets or []):
            if not isinstance(it, dict):
                continue
            wdef = dict(it)
            # Extract entity id from several possible keys
            ent = wdef.get("entity_id") or wdef.get("entity") or wdef.get("eid") or ""
            if isinstance(ent, str):
                ent = ent.strip()
            else:
                ent = ""
            # Determine type early to allow label/clock widgets without entity_id
            wtype = (wdef.get("type") or "").strip().lower() if isinstance(wdef.get("type"), str) else ""
            # Skip spacers explicitly; but allow label/clock widgets even with no entity
            if wtype == "spacer":
                continue
            # Skip invalid entries that have neither an entity nor a supported non-entity type
            if not ent and wtype not in ("label", "clock"):
                continue

            # Position aliases
            x = wdef.get("x", wdef.get("col"))
            y = wdef.get("y", wdef.get("row"))
            w = wdef.get("w", wdef.get("colspan"))
            h = wdef.get("h", wdef.get("rowspan"))
            xi = _coerce_int(x, 0)
            yi = _coerce_int(y, 0)
            wi = max(1, _coerce_int(w, 1))
            hi = max(1, _coerce_int(h, 1))

            # Determine type (if not set by user, infer from entity domain)
            dom = None
            obj = None
            if "." in ent:
                try:
                    dom, obj = ent.split(".", 1)
                except Exception:
                    dom, obj = None, None
            if not wtype:
                if dom == "light":
                    wtype = "light"
                elif dom in ("switch", "input_boolean"):
                    wtype = "switch"
                elif dom == "scene":
                    wtype = "scene"
                elif dom in ("script", "button"):
                    wtype = "button"
                elif dom == "person":
                    wtype = "person"
                else:
                    wtype = "sensor"

            # Build topics
            state_topic = None
            cmd_topic = None
            if dom and obj:
                state_topic = f"{base_stream}/{dom}/{obj}/state"
                if wtype in ("light", "switch", "button"):
                    cmd_topic = f"{base_cmd}/{ent}"

            # Compose normalized widget
            out: Dict[str, Any] = {
                "id": wdef.get("id") or f"p:{idx}:{ent}",
                "type": wtype,
                "entity_id": ent,
                "label": (wdef.get("label") or wdef.get("lbl") or ent),
                "x": xi, "y": yi, "w": wi, "h": hi,
                "state_topic": state_topic or "",
            }
            # Optional protection flag
            try:
                p = wdef.get("protected")
                if isinstance(p, (bool, int)):
                    out["protected"] = bool(p)
            except Exception:
                pass
            if cmd_topic:
                out["command_topic"] = cmd_topic
            # Optional unit for sensor displays
            try:
                u = wdef.get("unit")
                if isinstance(u, str) and u.strip():
                    out["unit"] = u.strip()
            except Exception:
                pass
            # Optional format (alignment, sizes, colors)
            try:
                fmt = wdef.get("format")
                if isinstance(fmt, dict) and len(fmt) > 0:
                    # Whitelist known keys to keep payload lean
                    allowed = {
                        "align", "vAlign", "textSize", "textColor", "bgColor",
                        "onTextColor", "offTextColor", "onBgColor", "offBgColor",
                        "wrap", "maxLines",
                    }
                    sanitized = {k: v for (k, v) in fmt.items() if k in allowed and isinstance(v, (str, int, float))}
                    if sanitized:
                        out["format"] = sanitized
            except Exception:
                pass
            # Optional brightness attr for lights
            if dom == "light" and obj:
                out["attr_topic"] = f"{base_stream}/{dom}/{obj}/attributes/brightness"

            # Label widget support: allow type=label without entity_id; carry 'text'
            if wtype == "label" and not ent:
                txt = wdef.get("text")
                if isinstance(txt, str):
                    out["text"] = txt
                # No topics for label; ensure state_topic empty
                out["state_topic"] = ""

            # Clock widget: no entity; purely local time render; support optional time_pattern
            if wtype == "clock":
                out["state_topic"] = ""
                pat = wdef.get("time_pattern")
                if isinstance(pat, str) and pat.strip():
                    out["time_pattern"] = pat.strip()

            # Weather widget: support attrs mapping and base attr topic
            if wtype == "weather" and dom == "weather" and obj:
                out["attr_base"] = f"{base_stream}/{dom}/{obj}/attributes"
                attrs = wdef.get("attrs")
                if isinstance(attrs, list) and attrs:
                    out["attrs"] = [a for a in attrs if isinstance(a, str)]
                units = wdef.get("attr_units")
                if isinstance(units, dict) and units:
                    # Keep simple key->str mapping
                    out["attr_units"] = {k: v for (k, v) in units.items() if isinstance(k, str) and isinstance(v, str)}

            norm_widgets.append(out)

        ui["widgets"] = norm_widgets
        try:
            _LOGGER.debug("build_config: device=%s normalized_widgets=%d", device_id, len(norm_widgets))
        except Exception:
            pass

        # Topics (settings/hello/status)
        topics = dict(raw.get("topics") or {})
        topics.setdefault("settings", f"{base_dev}/{device_id}/settings")
        topics.setdefault("hello",    f"{base_dev}/{device_id}/hello")
        topics.setdefault("status",   f"{base_dev}/{device_id}/status")

        # Attach last-known screen info if present on the device record (helps client layout decisions)
        if isinstance(dev.get("screen"), dict):
            device.setdefault("screen", dev.get("screen"))

        # Compose final document
        doc: Dict[str, Any] = {
            "version": 1,
            "device_id": device_id,
            # Device bucket may include screen info. keep_awake/brightness/orientation are controlled via HA entities
            "device": device or {},
            "ui": ui,
            "topics": topics,
        }

        try:
            _LOGGER.debug(
                "build_config: device=%s norm_widgets=%d base_dev=%s base_cmd=%s base_stream=%s",
                device_id, len(ui.get("widgets", [])),
                base_dev,
                FIXED_COMMAND_BASE,
                FIXED_STATESTREAM_BASE,
            )
        except Exception:
            pass
        return doc

    # ---------- device list helpers ----------
    def _dedupe_devices(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return devices unique by device_id; prefer entries with GUID or a non-empty profile."""
        by_id: Dict[str, Dict[str, Any]] = {}
        for d in devices:
            did = (d.get("device_id") or "").strip()
            if not did:
                continue
            prev = by_id.get(did)
            if not prev:
                by_id[did] = d
                continue
            # prefer one with guid, then with profile
            score_prev = (1 if prev.get("guid") else 0) + (1 if (prev.get("profile") or "") else 0)
            score_new  = (1 if d.get("guid") else 0) + (1 if (d.get("profile") or "") else 0)
            if score_new >= score_prev:
                by_id[did] = d
        return list(by_id.values())

    def _save_devices(self, devices: List[Dict[str, Any]]) -> None:
        cleaned = self._dedupe_devices(devices)
        # Preserve all existing options to avoid dropping profiles/mirror on device updates
        opts_now: Dict[str, Any] = dict(self.entry.options or {})
        # If profiles exist, ensure we do not inadvertently clear an existing device-specific profile
        existing_profiles: Dict[str, Any] = dict(opts_now.get(CONF_PROFILES, {}) or {})
        for rec in cleaned:
            did = (rec.get("device_id") or "").strip()
            # If profile field is empty but we already have a profile keyed by device_id, relink it
            if did and not (rec.get("profile") or "") and did in existing_profiles:
                _LOGGER.debug("save_devices: preserving existing profile for %s", did)
                rec["profile"] = did
        prev_keys = list(opts_now.keys())
        opts_now[CONF_DEVICES] = cleaned
        _LOGGER.debug(
            "save_devices: %d -> %d records; preserving option keys=%s",
            len(devices), len(cleaned), prev_keys,
        )
        # Write back options atomically (data portion untouched)
        self.hass.config_entries.async_update_entry(self.entry, options=opts_now)
        # Update in-memory caches immediately so subsequent logic sees new devices
        self._opts = dict(opts_now)
        self.cfg = {**self._data, **self._opts}
        # Best-effort profile persistence (does not block)
        try:
            # Only persist profiles if they exist (avoid empty file churn)
            if self.cfg.get(CONF_PROFILES):
                # Schedule in loop (fire and forget)
                # Persist profiles via storage helper (fire-and-forget)
                profiles = dict(self.cfg.get(CONF_PROFILES, {}) or {})
                self.hass.async_create_task(self._storage_helper.persist_profiles(profiles))
        except Exception:
            _LOGGER.debug("save_devices: profile persistence skipped due to error", exc_info=True)

    # ---------- mirror ----------
    async def _maybe_start_mirror(self, *, publish_snapshot: bool = True) -> None:
        # Mirror is always enabled; subscribe if any entities configured
        wanted = [w.lower() for w in list(self.cfg.get(CONF_MIRROR_ENTITIES, []) or []) if isinstance(w, str) and "." in w]

        if self._mirror_unsub:
            try: self._mirror_unsub()
            except Exception: pass
            self._mirror_unsub = None

        if not wanted:
            _LOGGER.debug("mirror enabled but empty entity list")
            return

        self._mirror_unsub = async_track_state_change_event(self.hass, wanted, self._on_state_changed)
        _LOGGER.debug("mirror started for %d entities", len(wanted))
        if publish_snapshot:
            await self.async_publish_snapshot()

    async def _on_state_changed(self, event: Event) -> None:
        ent_id = event.data.get("entity_id")
        if not isinstance(ent_id, str) or "." not in ent_id:
            return
        if not self._is_mirrored(ent_id):
            return

        new_state = event.data.get("new_state")
        if not new_state:
            return

        base = FIXED_STATESTREAM_BASE
        dom, obj = ent_id.split(".", 1)

        # State dedupe
        val = new_state.state
        if val in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            val = ""
        ent_key = f"{dom}.{obj}"
        if self._last_state.get(ent_key) != val:
            await mqtt.async_publish(self.hass, f"{base}/{dom}/{obj}/state", val, qos=0, retain=True)
            self._last_state[ent_key] = val

        # Attributes: publish only changes, track keys; clear removed keys to avoid stale retained attrs
        new_attr_map: Dict[str, str] = {}
        prev_attr_map: Dict[str, str] = dict(self._attr_vals_by_entity.get(ent_key, {}))
        for k, v in new_state.attributes.items():
            sv = str(v)
            new_attr_map[k] = sv
            if prev_attr_map.get(k) != sv:
                await mqtt.async_publish(self.hass, f"{base}/{dom}/{obj}/attributes/{k}", sv, qos=0, retain=True)
        # Purge removed keys
        removed_keys = set(prev_attr_map.keys()) - set(new_attr_map.keys())
        for k in removed_keys:
            await mqtt.async_publish(self.hass, f"{base}/{dom}/{obj}/attributes/{k}", "", qos=0, retain=True)
        self._attr_vals_by_entity[ent_key] = new_attr_map

    def _is_mirrored(self, entity_id: str) -> bool:
        wanted: List[str] = [str(x).lower() for x in (self.cfg.get(CONF_MIRROR_ENTITIES, []) or [])]
        return entity_id.lower() in wanted

    async def async_publish_snapshot(self) -> None:
        base = FIXED_STATESTREAM_BASE
        for ent_id in list(self.cfg.get(CONF_MIRROR_ENTITIES, []) or []):
            st = self.hass.states.get(ent_id)
            if not st: continue
            dom, obj = ent_id.split(".", 1)
            val = "" if st.state in (STATE_UNKNOWN, STATE_UNAVAILABLE) else st.state
            ent_key = f"{dom}.{obj}"
            # Write retained state and record cache
            await mqtt.async_publish(self.hass, f"{base}/{dom}/{obj}/state", val, qos=0, retain=True)
            self._last_state[ent_key] = val
            # Attributes: publish all on snapshot; record exact values for future dedupe/purge
            attr_map: Dict[str, str] = {}
            for k, v in st.attributes.items():
                sv = str(v)
                await mqtt.async_publish(self.hass, f"{base}/{dom}/{obj}/attributes/{k}", sv, qos=0, retain=True)
                attr_map[k] = sv
            self._attr_vals_by_entity[ent_key] = attr_map

    async def _purge_mirror_entities(self, removed: Set[str]) -> None:
        base = FIXED_STATESTREAM_BASE
        for ent_id in removed:
            if "." not in ent_id: continue
            dom, obj = ent_id.split(".", 1)
            await mqtt.async_publish(self.hass, f"{base}/{dom}/{obj}/state", "", qos=0, retain=True)
            # Purge per-attribute retained values we previously published
            prev = self._attr_vals_by_entity.pop(ent_id, {})
            for k in list(prev.keys()):
                await mqtt.async_publish(self.hass, f"{base}/{dom}/{obj}/attributes/{k}", "", qos=0, retain=True)

    # ---------- device channels ----------
    async def _on_device_hello(self, msg):
        _LOGGER.debug("device_hello: topic=%s payload_len=%d", getattr(msg, "topic", ""), len(_payload_to_str(msg)))
        raw = _payload_to_str(msg)
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            _LOGGER.warning("Bad hello payload on %s: %r", getattr(msg, "topic", ""), (raw or "")[:200])
            payload = {}
        topic: str = getattr(msg, "topic", "") or ""
        try:
            device_id = topic.split("/")[-2]
        except Exception:
            return

        guid = (payload.get("guid") or "").strip()
        prev_id = (payload.get("prev_id") or "").strip()
        # Optional screen info from client
        screen = payload.get("screen") if isinstance(payload.get("screen"), dict) else None

        # Always operate on a fresh snapshot of options to avoid overwriting concurrent edits
        opts = dict(self.entry.options or {})
        devices: List[Dict[str, Any]] = list(opts.get(CONF_DEVICES, []) or [])

        # If this device (by guid or incoming device_id) was explicitly purged via HA Delete Device, ignore hello
        try:
            await self._storage_helper.async_init()
            if self._storage_helper.is_purged_device(device_id=(device_id or None), guid=(guid or None)):
                _LOGGER.info("device_hello: ignoring purged device hello (device_id=%s guid=%s)", device_id, guid)
                return
        except Exception:
            _LOGGER.debug("device_hello: purged check failed", exc_info=True)

        # lookups
        by_id = {d.get("device_id"): d for d in devices if d.get("device_id")}
        by_guid = {d.get("guid"): d for d in devices if d.get("guid")}

        # 1) GUID match beats everything (rename if id differs)
        if guid and guid in by_guid:
            rec = by_guid[guid]
            old_id = rec.get("device_id")
            if old_id != device_id:
                rec["device_id"] = device_id
                # drop any other entries that already use the new id to avoid duplicates
                devices = [d for d in devices if (d is rec) or (d.get("device_id") != device_id)]
                if old_id:
                    ph = bool(self.entry.options.get("placeholder_on_remove", False))
                    await self._purge_device_retained(old_id, placeholder=ph)
                # Update screen info if provided
                if screen:
                    rec["screen"] = screen
                self._save_devices(devices)
                await self.async_publish_all_configs()
                # Ensure HA updates device list immediately
                self.schedule_entry_reload("hello_guid_rename")
                # Update HA device registry: migrate identifier and name to new device_id
                try:
                    if isinstance(old_id, str) and old_id:
                        await self._migrate_device_registry_identifier(old_id=old_id, new_id=device_id)
                except Exception:
                    _LOGGER.debug("hello GUID rename: device registry migration failed", exc_info=True)
            # online status
            base_dev = FIXED_DEVICE_BASE
            await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/status", "online", qos=0, retain=True)
            return

        # 2) prev_id path (fallback if guid unknown)
        if prev_id and prev_id in by_id:
            rec = by_id[prev_id]
            rec["device_id"] = device_id
            if guid:
                rec["guid"] = guid
            if screen:
                rec["screen"] = screen
            # remove any other entries for the target id
            devices = [d for d in devices if (d is rec) or (d.get("device_id") != device_id)]
            if prev_id:
                ph = bool(self.entry.options.get("placeholder_on_remove", False))
                await self._purge_device_retained(prev_id, placeholder=ph)
            self._save_devices(devices)
            await self.async_publish_all_configs()
            self.schedule_entry_reload("hello_prev_id_rename")
            # Update HA device registry: migrate identifier and name to new device_id
            try:
                if isinstance(prev_id, str) and prev_id:
                    await self._migrate_device_registry_identifier(old_id=prev_id, new_id=device_id)
            except Exception:
                _LOGGER.debug("hello prev_id rename: device registry migration failed", exc_info=True)
            base_dev = FIXED_DEVICE_BASE
            await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/status", "online", qos=0, retain=True)
            return

        # 3) new device (register)
        if device_id not in by_id:
            rec = {"device_id": device_id, "profile": ""}
            if guid:
                rec["guid"] = guid
            if screen:
                rec["screen"] = screen
            devices.append(rec)
            if device_id in (self.cfg.get(CONF_PROFILES, {}) or {}):
                _LOGGER.debug("device_hello: new device %s already has profile key -> will preserve on save", device_id)
            self._save_devices(devices)
            await self.async_publish_all_configs()
            self.schedule_entry_reload("hello_new_device")

        base_dev = FIXED_DEVICE_BASE
        await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/status", "online", qos=0, retain=True)
        # Re-publish retained settings from Store for this device on hello
        try:
            cur = self._storage_helper.get_device_settings(device_id)
            if cur:
                payload = json.dumps(cur)
                await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/settings", payload, qos=0, retain=True)
                async_dispatcher_send(self.hass, SIGNAL_DEVICE_SETTINGS_UPDATED, device_id, dict(cur))
        except Exception:
            _LOGGER.debug("hello settings republish skipped", exc_info=True)
        return


    async def _on_device_request(self, msg) -> None:
        _LOGGER.debug("device_request: topic=%s payload_len=%d", getattr(msg, "topic", ""), len(_payload_to_str(msg)))
        raw = _payload_to_str(msg)
        #raw = (msg.payload or b"").decode("utf-8", "ignore")
        try:
            req = json.loads(raw) if raw else {}
        except Exception:
            req = {}
        topic = getattr(msg, "topic", "") or ""
        # topic format: mqttdash/dev/<device_id>/request
        device_id = ""
        try:
            parts = topic.split("/")
            # [mqttdash, dev, <device_id>, request]
            if len(parts) >= 4:
                device_id = parts[2]
        except Exception:
            device_id = ""

        action = (req.get("action") or "").lower()
        if action == "snapshot":
            _LOGGER.debug("device_request: snapshot requested")
            await self.async_publish_snapshot()
        elif action == "onboard":
            # Explicit re-onboarding signal from client: clear purged markers and (re)publish config
            guid = (req.get("guid") or "").strip() if isinstance(req.get("guid"), str) else None
            try:
                # Remove purged markers so hello/config is honored
                await self._storage_helper.remove_purged(device_id=(device_id or None), guid=(guid or None))
            except Exception:
                _LOGGER.debug("device_request:onboard: failed to clear purged markers for %s / %s", device_id, guid, exc_info=True)

            # Ensure device exists in options; if missing, add placeholder record
            devices: List[Dict[str, Any]] = list(self.cfg.get(CONF_DEVICES, []) or [])
            by_id = {d.get("device_id"): d for d in devices if isinstance(d, dict)}
            if device_id and device_id not in by_id:
                rec: Dict[str, Any] = {"device_id": device_id, "profile": ""}
                if guid:
                    rec["guid"] = guid
                devices.append(rec)
                self._save_devices(devices)
                self.schedule_entry_reload("onboard_new_device")

            # Re-publish configs and status online; also rehydrate retained settings
            try:
                await self.async_publish_all_configs()
            except Exception:
                _LOGGER.debug("device_request:onboard: publish configs failed", exc_info=True)
            base_dev = FIXED_DEVICE_BASE
            if device_id:
                await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/status", "online", qos=0, retain=True)
                try:
                    cur = self._storage_helper.get_device_settings(device_id)
                    if cur:
                        payload = json.dumps(cur)
                        await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/settings", payload, qos=0, retain=True)
                        async_dispatcher_send(self.hass, SIGNAL_DEVICE_SETTINGS_UPDATED, device_id, dict(cur))
                except Exception:
                    _LOGGER.debug("onboard settings republish skipped", exc_info=True)

    async def _on_device_telemetry(self, msg) -> None:
        topic = getattr(msg, "topic", "") or ""
        payload = _payload_to_str(msg)
        _LOGGER.debug("device_telemetry: topic=%s payload=%s", topic, payload[:100])
        try:
            device_id = topic.split("/")[-3]  # mqttdash/dev/<device_id>/telemetry/...
        except Exception:
            return
        parts = topic.split("/")
        key = parts[-1] if parts else ""
        st = self._telemetry.setdefault(device_id, {})
        # battery (0-100), charging (on/off), orientation (string)
        if key == "battery":
            try:
                st["battery"] = int(payload)
            except Exception:
                pass
        elif key == "charging":
            st["charging"] = (payload.strip().lower() in ("on", "true", "1"))
        elif key == "orientation":
            st["orientation"] = payload.strip().lower()
        # expose to HA entities
        self.hass.data.setdefault("ha_mqtt_dash", {})["telemetry"] = self._telemetry

    async def _on_cmd(self, msg) -> None:
        topic = getattr(msg, "topic", "") or ""
        base_cmd = FIXED_COMMAND_BASE
        base_dev = FIXED_DEVICE_BASE

        raw = _payload_to_str(msg)
        try:
            cmd = json.loads(raw) if raw else {}
        except Exception:
            _LOGGER.warning("MQTT command bad JSON on %s: %r", topic, (raw or "")[:200])
            return

        _LOGGER.debug("MQTT command on %s: %s", topic, cmd)

        # Entity command path: <base_cmd>/<entity_id>
        if topic.startswith(f"{base_cmd}/") and len(topic) > len(base_cmd) + 1:
            entity_id = topic[len(base_cmd) + 1:]
            await self._handle_entity_command(entity_id, cmd)
            return

        # Admin path: <base_dev>/commands (or any other base)
        action = (cmd.get("action") or "").lower()
        if action == "rename":
            old_id = (cmd.get("old") or "").strip()
            new_id = (cmd.get("new") or "").strip()
            if old_id and new_id and old_id != new_id:
                await self.async_rename_device(old_id, new_id)
        elif action == "purge_device":
            dev = (cmd.get("device_id") or "").strip()
            if dev:
                await self.async_purge_device(dev)
        elif action == "publish_config":
            await self.async_publish_all_configs()
        elif action == "snapshot":
            await self.async_publish_snapshot()

    async def _handle_entity_command(self, entity_id: str, cmd: Dict[str, Any]) -> None:
        """Translate generic action payloads into HA service calls for entities."""
        if not entity_id or "." not in entity_id:
            return
        domain, _obj = entity_id.split(".", 1)
        st = self.hass.states.get(entity_id)
        if st is None:
            _LOGGER.warning("Command for unknown entity %s: %s", entity_id, cmd)
            return
        action = (cmd.get("action") or "").lower()
        data: Dict[str, Any] = {"entity_id": entity_id}

        # Map payload parameters
        if "brightness" in cmd:
            data["brightness"] = cmd.get("brightness")
        if "color_temp_mired" in cmd:
            data["color_temp"] = cmd.get("color_temp_mired")

        # Resolve service
        service = None
        if action in ("turn_on", "turn_off", "toggle"):
            service = action
            # Some domains use different services
            if domain == "scene" and action == "turn_on":
                service = "turn_on"
            elif domain == "script" and action in ("turn_on", "run"):
                service = "turn_on"
        elif action == "press" and domain == "button":
            service = "press"
        elif action == "set_level":
            # Best-effort: map to number.set_value if it's a number-like entity
            # Users should prefer domain-specific actions where possible
            if domain in ("number", "input_number"):
                await self.hass.services.async_call(domain, "set_value", {"entity_id": entity_id, "value": cmd.get("level")}, blocking=False)
                return

        # Default mapping for common domains (light/switch/input_boolean)
        if service and domain in ("light", "switch", "input_boolean", "scene", "script"):
            _LOGGER.debug("Calling service %s.%s with %s", domain, service, data)
            await self.hass.services.async_call(domain, service, data, blocking=False)
            return
        # Fallback: try a generic homeassistant.turn_on/off if applicable
        if service in ("turn_on", "turn_off", "toggle"):
            _LOGGER.debug("Calling fallback homeassistant.%s for %s", service, entity_id)
            await self.hass.services.async_call("homeassistant", service, {"entity_id": entity_id}, blocking=False)

    # ---------- maintenance ----------
    async def async_purge_device(self, device_id: str) -> None:
        _LOGGER.debug("purge_device: %s", device_id)
        # Explicit purge should fully clear retained topics without publishing placeholders
        await self._purge_device_retained(device_id, placeholder=False)
        # Notify the app that it was offboarded so it clears local settings and returns to welcome
        try:
            payload = json.dumps({"action": "offboard"})
            base_dev = FIXED_DEVICE_BASE
            # transient request channel (non-retained) so a connected app reacts immediately
            await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/request", payload, qos=0, retain=False)
            # also publish a retained offboard settings to ensure reconnecting apps see it
            await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/settings", payload, qos=0, retain=True)
        except Exception:
            _LOGGER.debug("purge_device: failed to publish offboard notice for %s", device_id, exc_info=True)
        devices: List[Dict[str, Any]] = list(self.cfg.get(CONF_DEVICES, []) or [])
        devices = [d for d in devices if d.get("device_id") != device_id]
        self._save_devices(devices)
        # Remove device and its entities from HA registries
        try:
            await self._remove_device_from_registry(device_id)
        except Exception:
            _LOGGER.debug("purge_device: registry removal failed for %s", device_id, exc_info=True)
        # Clear device settings and record a purged marker in Store to prevent resurrection
        try:
            await self._storage_helper.async_init()
            # remove device settings if present
            ds = self._storage_helper.storage.get("device_settings", {})
            if isinstance(ds, dict) and device_id in ds:
                ds.pop(device_id, None)
                if self._storage_helper._store:
                    await self._storage_helper._store.async_save(self._storage_helper.storage)
            # add purged marker by device_id (guid marker added in __init__ handler when available)
            await self._storage_helper.add_purged(device_id=device_id)
        except Exception:
            _LOGGER.debug("purge_device: failed to update Store for %s", device_id, exc_info=True)

    async def async_rename_device(self, old_id: str, new_id: str) -> None:
        """Update the human-readable device_id for a device.

        The device GUID (uuid) is the canonical identifier, used on device hello to
        match records. The device_id is a mutable name. When renamed, migrate any
        stored profile key from old_id to new_id, clear retained topics for old_id
        (respecting the placeholder setting), publish configs, and notify the old
        id so a connected client can self-rename.
        """
        _LOGGER.debug("rename_device: %s -> %s", old_id, new_id)
        devices: List[Dict[str, Any]] = list(self.cfg.get(CONF_DEVICES, []) or [])
        # Remove any pre-existing entries with new_id to avoid duplicates
        devices = [d for d in devices if (d.get("device_id") != new_id)]
        found = False
        for d in devices:
            if d.get("device_id") == old_id:
                d["device_id"] = new_id
                # Ensure profile follows the device id
                if d.get("profile") and d.get("profile") != new_id:
                    d["profile"] = new_id
                found = True
                break
        if not found:
            # Create a new blank record if old not found
            devices.append({"device_id": new_id, "profile": ""})
        # Migrate profile key in Store/options if present
        try:
            await self._storage_helper.async_init()
            profs = dict(self._storage_helper.storage.get("profiles") or {})
            if old_id in profs and new_id not in profs:
                profs[new_id] = profs.pop(old_id)
                await self._storage_helper.persist_profiles(profs)
        except Exception:
            _LOGGER.exception("rename_device: profile migration failed for %s -> %s", old_id, new_id)

        self._save_devices(devices)

        # Clear old retained topics; don't publish placeholder to avoid ghost device
        ph = bool(self.entry.options.get("placeholder_on_remove", False))
        await self._purge_device_retained(old_id, placeholder=ph)
        # Publish updated configs for all devices
        await self.async_publish_all_configs()
        # Migrate HA device registry identifiers and name to the new device_id (preserve entities)
        try:
            await self._migrate_device_registry_identifier(old_id=old_id, new_id=new_id)
        except Exception:
            _LOGGER.debug("rename_device: registry migration failed for %s -> %s", old_id, new_id, exc_info=True)
        # Notify the old-id device to rename itself (client will reconnect with prev_id)
        try:
            base_dev = FIXED_DEVICE_BASE
            payload = json.dumps({"action": "rename", "old": old_id, "new": new_id})
            await mqtt.async_publish(self.hass, f"{base_dev}/{old_id}/request", payload, qos=0, retain=False)
            _LOGGER.debug("rename_device: sent rename request to %s", old_id)
        except Exception:
            _LOGGER.debug("rename_device: failed to send rename request to %s", old_id, exc_info=True)

    async def _purge_device_retained(self, device_id: str, *, placeholder: bool = True) -> None:
        base_cfg = FIXED_CONFIG_BASE
        base_dev = FIXED_DEVICE_BASE
        topics = [
            f"{base_cfg}/{device_id}/config",
            f"{base_dev}/{device_id}/settings",
            f"{base_dev}/{device_id}/status",
            f"{base_dev}/{device_id}/hello",
            f"{base_dev}/{device_id}/heartbeat",
        ]
        _LOGGER.debug("purge_device_retained: clearing %d topics for %s", len(topics), device_id)
        for t in topics:
            await mqtt.async_publish(self.hass, t, "", qos=0, retain=True)
        if placeholder:
            # Optionally publish a placeholder unassigned config to let device recover quickly
            ph = {
                "version": 1,
                "device_id": device_id,
                "device": {},
                "ui": {"widgets": [], "banner": f"unassigned: set profile in HA for {device_id}"},
                "topics": {
                    "settings": f"{base_dev}/{device_id}/settings",
                    "hello": f"{base_dev}/{device_id}/hello",
                    "status": f"{base_dev}/{device_id}/status",
                },
            }
            payload = json.dumps(ph)
            _LOGGER.debug("purge_device_retained: publish placeholder %s bytes=%d", f"{base_cfg}/{device_id}/config", len(payload))
            await mqtt.async_publish(self.hass, f"{base_cfg}/{device_id}/config", payload, qos=0, retain=True)

    async def async_publish_device_settings(self, device_id: str, *, brightness: Optional[float] = None, keep_awake: Optional[bool] = None, orientation: Optional[str] = None) -> None:
        """Publish a settings JSON for the device to apply immediately on the client.
        App consumes keep_awake and brightness.
        """
        if not device_id:
            return
        base_dev = FIXED_DEVICE_BASE
        patch: Dict[str, Any] = {}
        if brightness is not None:
            patch["brightness"] = float(brightness)
        if keep_awake is not None:
            patch["keep_awake"] = bool(keep_awake)
        if isinstance(orientation, str) and orientation in ("auto", "portrait", "landscape"):
            patch["orientation"] = orientation
        if not patch:
            return
        try:
            payload = json.dumps(patch, separators=(",", ":"))
        except Exception:
            return
        _LOGGER.debug("publish_device_settings: %s payload=%s", f"{base_dev}/{device_id}/settings", payload)
        # Retain last settings so late subscribers pick up current brightness/keep_awake/orientation
        await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/settings", payload, qos=0, retain=True)
        # Persist to Store for restart survival
        try:
            cur = await self._storage_helper.update_device_settings(device_id, patch)
            # Notify HA entities of device setting change
            async_dispatcher_send(self.hass, SIGNAL_DEVICE_SETTINGS_UPDATED, device_id, dict(cur))
        except Exception:
            _LOGGER.exception("store save failed (device_settings)")

    async def async_prune_unassigned(self) -> None:
        """Remove devices with no profile and no GUID, and purge their retained topics."""
        devices: List[Dict[str, Any]] = list(self.cfg.get(CONF_DEVICES, []) or [])
        keep: List[Dict[str, Any]] = []
        removed: List[str] = []
        for d in devices:
            did = (d.get("device_id") or "").strip()
            prof = (d.get("profile") or "").strip()
            guid = (d.get("guid") or "").strip()
            if did and (prof or guid):
                keep.append(d)
            elif did:
                removed.append(did)
        if removed:
            _LOGGER.debug("pruning %d unassigned device(s): %s", len(removed), removed)
            for did in removed:
                await self._purge_device_retained(did)
        self._save_devices(keep)
        await self.async_publish_all_configs()

    # ---------- device actions ----------
    async def async_publish_device_action(self, device_id: str, *, action: str) -> None:
        if not device_id or not action:
            return
        base_dev = FIXED_DEVICE_BASE
        payload = json.dumps({"action": action})
        # Send to both request (transient trigger) and settings (retained reflection) topics
        _LOGGER.debug("publish_device_action: %s action=%s", device_id, action)
        await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/request", payload, qos=0, retain=False)
        # Publish action on settings as NON-retained to avoid stale reloads after reconnects
        await mqtt.async_publish(self.hass, f"{base_dev}/{device_id}/settings", payload, qos=0, retain=False)

    # ---------- persistence (profiles) ----------
    def _profiles_path(self) -> str:
        # Deprecated: moved to StorageHelper
        return self.hass.config.path("ha_mqtt_dash_profiles.json")

    async def _remove_device_from_registry(self, device_id: str) -> None:
        """Remove device and all its entities from HA registries by identifier."""
        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)
        dev = None
        for d in list(dev_reg.devices.values()):
            if (DOMAIN, device_id) in (d.identifiers or set()):
                dev = d
                break
        if not dev:
            return
        ents = list(ent_reg.async_entries_for_device(dev.id, include_disabled_entities=True))
        for e in ents:
            try:
                ent_reg.async_remove(e.entity_id)
            except Exception:
                _LOGGER.debug("entity removal failed: %s", e.entity_id, exc_info=True)
        try:
            dev_reg.async_remove_device(dev.id)
        except Exception:
            _LOGGER.debug("device removal failed: %s", device_id, exc_info=True)

    async def _update_device_registry_name(self, *, identifier_device_id: str, display_name: str) -> None:
        """Update the HA device's display name for the given identifier.

        This keeps the device's name in HA in sync with the mutable device_id label even
        when entities are still attached to the old identifier. Does not change identifiers.
        """
        dev_reg = dr.async_get(self.hass)
        for d in list(dev_reg.devices.values()):
            if (DOMAIN, identifier_device_id) in (d.identifiers or set()):
                try:
                    dev_reg.async_update_device(d.id, name=display_name)
                except Exception:
                    _LOGGER.debug("device name update failed for %s", identifier_device_id, exc_info=True)
                break

    async def _migrate_device_registry_identifier(self, *, old_id: str, new_id: str) -> None:
        """Change HA device identifier from (DOMAIN, old_id) to (DOMAIN, new_id) and update display name.

        - If another device already exists with (DOMAIN, new_id) and has no entities, remove it.
        - Otherwise, prefer updating the existing device bearing old_id to avoid entity churn.
        """
        if not (isinstance(old_id, str) and isinstance(new_id, str) and old_id and new_id and old_id != new_id):
            return
        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)

        target = None
        for d in list(dev_reg.devices.values()):
            if (DOMAIN, old_id) in (d.identifiers or set()):
                target = d
                break
        if not target:
            return

        duplicate = None
        for d in list(dev_reg.devices.values()):
            if (DOMAIN, new_id) in (d.identifiers or set()):
                duplicate = d
                break

        # Remove empty duplicate device (if any) to prevent identifier collision
        if duplicate and duplicate.id != target.id:
            ents = ent_reg.async_entries_for_device(duplicate.id, include_disabled_entities=True)
            if not ents:
                try:
                    dev_reg.async_remove_device(duplicate.id)
                except Exception:
                    _LOGGER.debug("unable to remove duplicate device for %s", new_id, exc_info=True)
            else:
                # If duplicate has entities, avoid destructive merge; update only target name
                try:
                    dev_reg.async_update_device(target.id, name=new_id)
                except Exception:
                    _LOGGER.debug("device name update failed during guarded migration %s->%s", old_id, new_id, exc_info=True)
                return

        # Update identifiers and name on the target device
        new_identifiers = set(target.identifiers or set())
        if (DOMAIN, old_id) in new_identifiers:
            new_identifiers.remove((DOMAIN, old_id))
        new_identifiers.add((DOMAIN, new_id))
        try:
            dev_reg.async_update_device(target.id, identifiers=new_identifiers, name=new_id)
        except Exception:
            _LOGGER.debug("device identifier/name update failed %s->%s", old_id, new_id, exc_info=True)
