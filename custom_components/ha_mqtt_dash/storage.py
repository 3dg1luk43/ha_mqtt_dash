from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Set
import hashlib
import time

from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.helpers.storage import Store  # type: ignore

from .const import (
    CONF_DEVICES,
    CONF_PROFILES,
    STORAGE_KEY,
    STORAGE_VERSION,
)


_LOGGER = logging.getLogger(__name__)


class StorageHelper:
    """Encapsulate HA Store usage and migration for profiles and device settings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store | None = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        self._storage: Dict[str, Any] = {"profiles": {}, "device_settings": {}, "purged_devices": [], "purged_guids": []}

    @property
    def storage(self) -> Dict[str, Any]:
        return self._storage

    def _profiles_path(self) -> str:
        # Deprecated: no longer used; Store is the only persistence backend
        return self.hass.config.path("ha_mqtt_dash_profiles.json")

    async def async_init(self) -> None:
        """Load HA Store. Store is the sole canonical source. Mirror to options for UI only."""
        # 1) Load existing store
        loaded = None
        try:
            loaded = await self._store.async_load() if self._store else None
        except Exception:
            _LOGGER.exception("store load failed")
        if isinstance(loaded, dict):
            self._storage = {**{"profiles": {}, "device_settings": {}, "purged_devices": [], "purged_guids": []}, **loaded}
        else:
            self._storage = {"profiles": {}, "device_settings": {}, "purged_devices": [], "purged_guids": []}

        # 2) Use Store contents as canonical; no options fallback
        store_profiles = dict(self._storage.get("profiles", {}) or {})
        self._storage["profiles"] = dict(store_profiles)
        # Ensure keys exist
        if not isinstance(self._storage.get("purged_devices"), list):
            self._storage["purged_devices"] = []
        if not isinstance(self._storage.get("purged_guids"), list):
            self._storage["purged_guids"] = []
        # Compute and persist metadata
        try:
            s = json.dumps(self._storage["profiles"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            phash = hashlib.sha256(s.encode("utf-8")).hexdigest()
            self._storage["profiles_meta"] = {"hash": phash, "updated_at": int(time.time())}
        except Exception:
            pass
        try:
            if self._store:
                await self._store.async_save(self._storage)
            _LOGGER.debug("store: confirmed profiles on init (%d)", len(self._storage.get("profiles") or {}))
        except Exception:
            _LOGGER.exception("store save after init failed")

        new_opts = {**(self.entry.options or {})}
        new_opts[CONF_PROFILES] = dict(self._storage.get("profiles") or {})
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)

    # Purged devices helpers
    def is_purged_device(self, *, device_id: str | None = None, guid: str | None = None) -> bool:
        try:
            if device_id and device_id in (self._storage.get("purged_devices") or []):
                return True
            if guid and guid in (self._storage.get("purged_guids") or []):
                return True
        except Exception:
            pass
        return False

    async def add_purged(self, *, device_id: str | None = None, guid: str | None = None) -> None:
        changed = False
        try:
            if device_id:
                lst = self._storage.setdefault("purged_devices", [])
                if device_id not in lst:
                    lst.append(device_id)
                    changed = True
            if guid:
                lstg = self._storage.setdefault("purged_guids", [])
                if guid not in lstg:
                    lstg.append(guid)
                    changed = True
            if changed and self._store:
                await self._store.async_save(self._storage)
        except Exception:
            _LOGGER.exception("store save failed (purged add)")

    async def remove_purged(self, *, device_id: str | None = None, guid: str | None = None) -> None:
        changed = False
        try:
            if device_id and device_id in (self._storage.get("purged_devices") or []):
                lst = list(self._storage.get("purged_devices") or [])
                lst = [x for x in lst if x != device_id]
                self._storage["purged_devices"] = lst
                changed = True
            if guid and guid in (self._storage.get("purged_guids") or []):
                lstg = list(self._storage.get("purged_guids") or [])
                lstg = [x for x in lstg if x != guid]
                self._storage["purged_guids"] = lstg
                changed = True
            if changed and self._store:
                await self._store.async_save(self._storage)
        except Exception:
            _LOGGER.exception("store save failed (purged remove)")

    def get_device_settings(self, device_id: str) -> Dict[str, Any]:
        try:
            ds = self._storage.get("device_settings", {}) if isinstance(self._storage, dict) else {}
            cur = ds.get(device_id)
            return dict(cur) if isinstance(cur, dict) else {}
        except Exception:
            return {}

    async def update_device_settings(self, device_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Merge patch into device settings in Store and persist. Returns merged dict."""
        ds = self._storage.setdefault("device_settings", {})
        cur_src = ds.get(device_id)
        cur = dict(cur_src) if isinstance(cur_src, dict) else {}
        cur.update(patch)
        ds[device_id] = cur
        try:
            if self._store:
                await self._store.async_save(self._storage)
        except Exception:
            _LOGGER.exception("store save failed (device_settings)")
        return dict(cur)

    async def persist_profiles(self, profiles: Dict[str, Any]) -> Dict[str, Any]:
        """Persist profiles to Store and mirror into options. Returns the saved profiles copy."""
        self._storage["profiles"] = dict(profiles)
        # Update metadata
        try:
            s = json.dumps(self._storage["profiles"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            phash = hashlib.sha256(s.encode("utf-8")).hexdigest()
            self._storage["profiles_meta"] = {"hash": phash, "updated_at": int(time.time())}
        except Exception:
            pass
        # Save to Store
        try:
            if self._store:
                await self._store.async_save(self._storage)
            _LOGGER.debug("store: saved profiles (%d)", len(profiles))
        except Exception:
            _LOGGER.exception("store save failed (profiles)")
        # Mirror to options so HA UI reflects latest immediately
        try:
            new_opts = {**(self.entry.options or {})}
            new_opts[CONF_PROFILES] = dict(profiles)
            self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        except Exception:
            _LOGGER.exception("options mirror failed (profiles)")
        return dict(self._storage.get("profiles") or {})

    async def prune_unused_profiles(self, profiles: Dict[str, Any], devices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Remove unreferenced profiles, save, and mirror to options. Returns remaining profiles."""
        profs = dict(profiles or {})
        if not profs:
            return profs
        used: Set[str] = set()
        for d in devices:
            pk = (d.get("profile") or "").strip()
            did = (d.get("device_id") or "").strip()
            if pk:
                used.add(pk)
            if did:
                used.add(did)
        keep_always = {"default"}
        remove = [k for k in list(profs.keys()) if k not in used and k not in keep_always]
        for k in remove:
            profs.pop(k, None)
        self._storage["profiles"] = dict(profs)
        try:
            if self._store:
                await self._store.async_save(self._storage)
        except Exception:
            _LOGGER.exception("store save failed (prune)")
        # Mirror to options
        try:
            new_opts = {**(self.entry.options or {})}
            new_opts[CONF_PROFILES] = dict(profs)
            self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        except Exception:
            _LOGGER.exception("options mirror failed (prune)")
        _LOGGER.debug("pruned unused profiles: removed=%s remaining=%d", remove, len(profs))
        return profs
