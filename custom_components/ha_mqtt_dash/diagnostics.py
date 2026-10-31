"""Download diagnostics (Settings > Devices & services > iPad MQTT Dashboard > menu).

Replaces the old dump_* services: panels, their stored profiles (summarised)
and the config each panel actually receives, telemetry, battery care and last
contact. Secrets (API keys, passwords, tokens, credentials in URLs) are redacted.
"""
from __future__ import annotations

import re
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.core import HomeAssistant  # type: ignore

from .const import CONF_DEVICES, CONF_PROFILES, DOMAIN

REDACTED = "**REDACTED**"
_SECRET_KEY = re.compile(r"(api_?key|apikey|pass(word|wd)?$|token|secret|auth)", re.I)
_URL_CREDS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s:]+(:[^/@\s]*)?@", re.I)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (REDACTED if isinstance(k, str) and _SECRET_KEY.search(k) and v not in (None, "") else redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _URL_CREDS.sub(lambda m: f"{m.group('scheme')}{REDACTED}@", value)
    return value


def _widgets(profile: Any):
    if not isinstance(profile, dict):
        return
    for src in (profile, profile.get("ui") if isinstance(profile.get("ui"), dict) else {}):
        for w in src.get("widgets") or []:
            if isinstance(w, dict):
                yield w
        for page in src.get("pages") or []:
            for w in (page.get("widgets") or []) if isinstance(page, dict) else []:
                if isinstance(w, dict):
                    yield w


def profile_summary(profile: Any) -> Dict[str, Any]:
    ui = profile.get("ui") if isinstance(profile, dict) and isinstance(profile.get("ui"), dict) else {}
    types: Dict[str, int] = {}
    for w in _widgets(profile):
        t = str(w.get("type") or "?")
        types[t] = types.get(t, 0) + 1
    return {"pages": len(ui.get("pages") or []) or 1, "widgets": sum(types.values()), "types": types,
            "grid": ui.get("grid")}


def _panel(bridge, did: str) -> Dict[str, Any]:
    dev = next((d for d in (bridge.cfg.get(CONF_DEVICES) or []) if isinstance(d, dict) and d.get("device_id") == did), {})
    out: Dict[str, Any] = {
        "record": dev,
        "settings": bridge.get_device_settings(did),
        "telemetry": (bridge._telemetry or {}).get(did, {}),
        "last_contact": bridge.last_contact.get(did),
        "battery_care": {"settings": bridge.battery.settings(did), "status": bridge.battery.status(did),
                         **bridge.battery.diagnostics(did)},
    }
    try:
        out["published_config"] = bridge._build_config_for_device(dev or {"device_id": did})
    except Exception as err:  # pragma: no cover - diagnostics must not fail
        out["published_config"] = f"build failed: {err!r}"
    return out


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> Dict[str, Any]:
    bridge = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    options = {k: v for k, v in (entry.options or {}).items() if k != CONF_PROFILES}
    if bridge is None:
        return redact({"loaded": False, "options": options})
    profiles = dict(bridge.cfg.get(CONF_PROFILES) or {})
    ids = [d.get("device_id") for d in (bridge.cfg.get(CONF_DEVICES) or []) if isinstance(d, dict) and d.get("device_id")]
    return redact({
        "loaded": True,
        "options": options,
        "profiles": {k: profile_summary(v) for k, v in profiles.items()},
        "mirrored_entities": len(getattr(bridge, "_mirror_wanted", []) or []),
        "panels": {did: _panel(bridge, did) for did in ids},
    })


async def async_get_device_diagnostics(hass: HomeAssistant, entry: ConfigEntry, device) -> Dict[str, Any]:
    bridge = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    did = next((i for d, i in (device.identifiers or set()) if d == DOMAIN), None)
    if bridge is None or not did:
        return {"loaded": bridge is not None, "panel": did}
    profile = (bridge.cfg.get(CONF_PROFILES) or {}).get(did)
    return redact({"panel": did, "profile": profile_summary(profile) if profile else None, **_panel(bridge, did)})
