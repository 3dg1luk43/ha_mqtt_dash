"""Dashboard editor hosted inside Home Assistant.

The profile editor's built files ship in ``editor/`` and are served at
``/ha_mqtt_dash_static/editor``. They're shown as an admin-only panel at
``/mqttdash-editor``, linked from the integration options and each panel's
device page. The sidebar entry is off by default (it's used rarely) and can be
switched on in the options.

Embedded, the editor uses Home Assistant's own logged-in connection and talks
to these admin-only WebSocket commands, so no OAuth, tokens or API-access
window are involved:

* ``ha_mqtt_dash/devices``        → registered panels (+ battery / profile flag)
* ``ha_mqtt_dash/get_profile``    → the stored profile for a panel
* ``ha_mqtt_dash/apply_profile``  → save a profile and push it to the panel
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import voluptuous as vol  # type: ignore

from homeassistant.components import frontend, panel_custom, websocket_api  # type: ignore
from homeassistant.core import HomeAssistant, callback  # type: ignore

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_URL = "mqttdash-editor"
STATIC_URL = "/ha_mqtt_dash_static/editor"
EDITOR_DIR = Path(__file__).parent / "editor"
PANEL_JS = Path(__file__).parent / "frontend" / "mqttdash-editor-panel.js"
PANEL_JS_URL = "/ha_mqtt_dash_static/panel/mqttdash-editor-panel.js"
_DATA_KEY = f"{DOMAIN}_editor_registered"
_SIDEBAR_KEY = f"{DOMAIN}_editor_sidebar"
SIDEBAR_TITLE = "iPad Dashboards"
SIDEBAR_ICON = "mdi:tablet-dashboard"

# Profile limits (a profile is published retained to MQTT and parsed on an iPad 1)
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_MAX_PAGES = 20
_MAX_WIDGETS_PER_PAGE = 200
_MAX_TOTAL_WIDGETS = 500
_MAX_STRING_LEN = 4096  # per string value anywhere in the profile


def _sanitise_profile(raw: object) -> dict:
    """Round-trip through JSON (strips non-serialisable objects) then validate
    structure and limits.  Raises ValueError with a human-readable message."""
    if not isinstance(raw, dict):
        raise ValueError("'profile' must be a JSON object")
    try:
        cleaned: dict = json.loads(json.dumps(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"profile is not JSON-serialisable: {exc}") from exc

    # Structural check
    pages = cleaned.get("pages")
    if pages is not None:
        if not isinstance(pages, list):
            raise ValueError("profile.pages must be an array")
        if len(pages) > _MAX_PAGES:
            raise ValueError(f"profile.pages exceeds limit of {_MAX_PAGES}")
        total = 0
        for i, page in enumerate(pages):
            if not isinstance(page, dict):
                raise ValueError(f"profile.pages[{i}] must be an object")
            widgets = page.get("widgets")
            if widgets is not None:
                if not isinstance(widgets, list):
                    raise ValueError(f"profile.pages[{i}].widgets must be an array")
                if len(widgets) > _MAX_WIDGETS_PER_PAGE:
                    raise ValueError(
                        f"profile.pages[{i}] exceeds {_MAX_WIDGETS_PER_PAGE} widgets"
                    )
                total += len(widgets)
                for j, w in enumerate(widgets):
                    if not isinstance(w, dict):
                        raise ValueError(
                            f"profile.pages[{i}].widgets[{j}] must be an object"
                        )
        if total > _MAX_TOTAL_WIDGETS:
            raise ValueError(f"profile total widget count exceeds {_MAX_TOTAL_WIDGETS}")

    # String-length check (iterative BFS to avoid recursion limit)
    queue: list = [cleaned]
    while queue:
        node = queue.pop()
        if isinstance(node, str):
            if len(node) > _MAX_STRING_LEN:
                raise ValueError(
                    f"A string value in the profile exceeds {_MAX_STRING_LEN} characters"
                )
        elif isinstance(node, dict):
            queue.extend(node.values())
        elif isinstance(node, list):
            queue.extend(node)

    return cleaned



def _bridge(hass: HomeAssistant):
    for b in (hass.data.get(DOMAIN) or {}).values():
        if hasattr(b, "_build_config_for_device"):
            return b
    return None


async def async_setup_editor(hass: HomeAssistant, *, sidebar: bool = False) -> None:
    """Register static files + WebSocket commands once per HA run, and the panel
    (again when the sidebar option changes)."""
    if not hass.data.get(_DATA_KEY):
        hass.data[_DATA_KEY] = True
        websocket_api.async_register_command(hass, ws_devices)
        websocket_api.async_register_command(hass, ws_get_profile)
        websocket_api.async_register_command(hass, ws_apply_profile)
        if (EDITOR_DIR / "index.html").is_file():
            from homeassistant.components.http import StaticPathConfig  # type: ignore
            await hass.http.async_register_static_paths([
                StaticPathConfig(STATIC_URL, str(EDITOR_DIR), False),
                StaticPathConfig(PANEL_JS_URL, str(PANEL_JS), False),
            ])
        else:
            _LOGGER.warning("Dashboard editor files missing (%s); panel not available", EDITOR_DIR)
            hass.data[_DATA_KEY] = "no_files"
    if hass.data.get(_DATA_KEY) is not True:
        return
    if hass.data.get(_SIDEBAR_KEY) == sidebar and PANEL_URL in (hass.data.get(frontend.DATA_PANELS) or {}):
        return  # already registered as wanted (entry reload)
    async_remove_editor_panel(hass)
    # Custom panel (not the built-in "iframe" one): no HA toolbar, so the
    # editor uses the full content area. Without sidebar_title it isn't listed
    # in the sidebar (default; reached from the options flow / device page).
    try:
        version = int(PANEL_JS.stat().st_mtime)  # cache-bust the module on updates
    except OSError:
        version = 0
    extra = {"sidebar_title": SIDEBAR_TITLE, "sidebar_icon": SIDEBAR_ICON} if sidebar else {}
    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL,
            webcomponent_name="mqttdash-editor-panel",
            module_url=f"{PANEL_JS_URL}?v={version}",
            embed_iframe=False,
            require_admin=True,
            config={"url": f"{STATIC_URL}/index.html?embedded=1"},
            **extra,
        )
        hass.data[_SIDEBAR_KEY] = sidebar
    except ValueError:
        pass  # registered meanwhile


@callback
def async_remove_editor_panel(hass: HomeAssistant) -> None:
    if PANEL_URL not in (hass.data.get(frontend.DATA_PANELS) or {}):
        return
    try:
        frontend.async_remove_panel(hass, PANEL_URL)
    except Exception:  # pragma: no cover - panel may not exist
        pass


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/devices"})
@websocket_api.require_admin
@callback
def ws_devices(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    bridge = _bridge(hass)
    if bridge is None:
        connection.send_error(msg["id"], "not_loaded", "iPad MQTT Dashboard isn't loaded")
        return
    profiles = dict((bridge._storage_helper.storage or {}).get("profiles") or {})
    out = []
    for d in list(bridge.cfg.get("devices", []) or []):
        did = (d.get("device_id") or "").strip() if isinstance(d, dict) else ""
        if not did:
            continue
        tel = (bridge._telemetry or {}).get(did, {})
        orientation = (bridge.get_device_settings(did) or {}).get("orientation")
        if orientation not in ("portrait", "landscape"):
            scr = d.get("screen") if isinstance(d.get("screen"), dict) else {}
            orientation = scr.get("orientation") or tel.get("orientation")
        out.append({
            "orientation": orientation,
            "device_id": did,
            "has_profile": did in profiles,
            "battery": tel.get("battery"),
            "screen": d.get("screen") if isinstance(d.get("screen"), dict) else None,
        })
    connection.send_result(msg["id"], {"devices": out})


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/get_profile",
    vol.Required("device_id"): str,
})
@websocket_api.require_admin
@callback
def ws_get_profile(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    bridge = _bridge(hass)
    if bridge is None:
        connection.send_error(msg["id"], "not_loaded", "iPad MQTT Dashboard isn't loaded")
        return
    profile: Optional[dict] = ((bridge._storage_helper.storage or {}).get("profiles") or {}).get(msg["device_id"])
    connection.send_result(msg["id"], {"device_id": msg["device_id"], "profile": profile})


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/apply_profile",
    vol.Required("device_id"): str,
    vol.Required("profile"): dict,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_apply_profile(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    bridge = _bridge(hass)
    if bridge is None:
        connection.send_error(msg["id"], "not_loaded", "iPad MQTT Dashboard isn't loaded")
        return
    device_id = msg["device_id"]
    if not _DEVICE_ID_RE.match(device_id):
        connection.send_error(msg["id"], "invalid_device_id", "1–64 chars: letters, digits, - and _")
        return
    try:
        profile = _sanitise_profile(msg["profile"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_profile", str(err))
        return
    helper = bridge._storage_helper
    profs = dict((helper.storage or {}).get("profiles") or {})
    profs[device_id] = profile
    await helper.persist_profiles(profs)
    bridge.schedule_republish_reload("editor_panel")
    user = getattr(connection, "user", None)
    _LOGGER.info("editor: applied profile for '%s' (user '%s')", device_id, getattr(user, "name", "?"))
    connection.send_result(msg["id"], {"status": "ok", "device_id": device_id})
