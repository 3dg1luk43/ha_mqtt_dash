"""Custom HTTP endpoint for the profile editor 'Send to HA' feature.

Registers two routes directly on hass.http.app.router (bypassing
HomeAssistantView / aiohttp_cors) so we can emit exactly the CORS headers
we need without conflicting with HA's aiohttp_cors plumbing:

  OPTIONS /api/ha_mqtt_dash/apply_profile  — CORS preflight (no auth)
  POST    /api/ha_mqtt_dash/apply_profile  — apply a profile

Security model
--------------
- Local-network only: requests from non-RFC-1918/loopback addresses are
  rejected before any further processing.
- Rate-limited: max 20 requests per IP per 60-second sliding window.
- Bearer token required: validated via hass.auth.async_validate_access_token.
- Active user required: token must belong to a non-disabled HA account.
- Content-Type enforced: must be application/json.
- Body size capped at 512 KB (checked via header and at read time).
- device_id sanitised: alphanumeric + hyphens/underscores, max 64 chars.
- Profile sanitised: round-tripped through json.dumps/loads; structure and
  widget-count limits enforced; all string values length-capped.

CORS
----
Both handlers add 'Access-Control-Allow-Origin: *' explicitly.  We register
the routes directly on hass.http.app.router so aiohttp_cors never sees them
and cannot register a conflicting OPTIONS handler.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import re
import time

from aiohttp import web

from .const import DOMAIN, CONF_API_UNTIL_KEY
from .storage import StorageHelper

_LOGGER = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_MAX_BODY_BYTES       = 512 * 1024          # 512 KB
_DEVICE_ID_RE         = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')
_VIEW_PATH            = "/api/ha_mqtt_dash/apply_profile"
_ENTITIES_PATH        = "/api/ha_mqtt_dash/entities"

# Profile structural limits
_MAX_PAGES            = 20
_MAX_WIDGETS_PER_PAGE = 200
_MAX_TOTAL_WIDGETS    = 500
_MAX_STRING_LEN       = 4096               # per string value anywhere in profile

# Rate limiting: sliding window per source IP
_RATE_LIMIT_KEY       = f"{DOMAIN}_rl"    # hass.data key
_RATE_MAX_REQUESTS    = 20
_RATE_WINDOW_SECS     = 60.0

_CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age":       "3600",
}

_CORS_HEADERS_GET = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization",
    "Access-Control-Max-Age":       "3600",
}

# ── Local-network allow-list ───────────────────────────────────────────────────

_LOCAL_NETS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),    # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),     # RFC-1918 class A
    ipaddress.ip_network("172.16.0.0/12"),  # RFC-1918 class B
    ipaddress.ip_network("192.168.0.0/16"), # RFC-1918 class C
    ipaddress.ip_network("169.254.0.0/16"), # IPv4 link-local
    ipaddress.ip_network("::1/128"),        # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),       # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),      # IPv6 link-local
]


def _is_local(ip_str: str | None) -> bool:
    if not ip_str:
        return False
    ip_str = ip_str.split("%")[0].strip("[]")
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _LOCAL_NETS)
    except ValueError:
        return False


# ── Rate limiter ───────────────────────────────────────────────────────────────

def _allow_rate(hass, ip: str) -> bool:
    """Return True if within limit; False if this IP is over the limit."""
    now  = time.monotonic()
    data = hass.data.setdefault(_RATE_LIMIT_KEY, {})
    ts   = [t for t in data.get(ip, []) if now - t < _RATE_WINDOW_SECS]
    if len(ts) >= _RATE_MAX_REQUESTS:
        data[ip] = ts
        return False
    ts.append(now)
    data[ip] = ts
    # Prune stale IPs to prevent unbounded growth
    if len(data) > 500:
        cutoff = now - _RATE_WINDOW_SECS
        hass.data[_RATE_LIMIT_KEY] = {
            k: v for k, v in data.items()
            if any(t > cutoff for t in v)
        }
    return True


# ── Profile validation ─────────────────────────────────────────────────────────

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _err(status: int, text: str) -> web.Response:
    return web.Response(
        status=status, text=text,
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ── Route handlers ─────────────────────────────────────────────────────────────

async def _options_handler(request: web.Request) -> web.Response:
    """CORS preflight — no authentication required."""
    return web.Response(headers=_CORS_HEADERS)


async def _post_handler(request: web.Request) -> web.Response:
    """Apply a profile sent from the profile editor."""
    hass   = request.app["hass"]
    remote = request.remote  # resolved by HA's real-IP middleware

    # ── -1. API enabled check ─────────────────────────────────────────────
    api_until = hass.data.get(CONF_API_UNTIL_KEY, 0)
    if time.time() > api_until:
        return _err(
            403,
            "API access is disabled. Enable it in Integration Options → API Access.",
        )

    # ── 0. Local-network guard ────────────────────────────────────────────
    if not _is_local(remote):
        _LOGGER.warning("apply_profile: blocked non-local IP %s", remote)
        return _err(403, "This endpoint is only accessible on a local network")

    # ── 1. Rate limit ─────────────────────────────────────────────────────
    if not _allow_rate(hass, remote or ""):
        _LOGGER.warning("apply_profile: rate limit exceeded for %s", remote)
        return _err(429, "Too many requests — please wait before retrying")

    # ── 2. Content-Type ───────────────────────────────────────────────────
    if "application/json" not in (request.content_type or ""):
        return _err(415, "Content-Type must be application/json")

    # ── 3. Body size guard (header) ───────────────────────────────────────
    if (request.content_length or 0) > _MAX_BODY_BYTES:
        return _err(413, f"Request body too large (max {_MAX_BODY_BYTES} bytes)")

    # ── 4. Bearer token auth ──────────────────────────────────────────────
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return _err(401, "Missing or malformed Authorization header")
    token_str = auth_header[7:].strip()
    if not token_str:
        return _err(401, "Empty Bearer token")

    refresh_token = hass.auth.async_validate_access_token(token_str)
    if refresh_token is None:
        _LOGGER.warning("apply_profile: rejected invalid/expired token from %s", remote)
        return _err(401, "Invalid or expired token")

    # ── 5. Active-user check ──────────────────────────────────────────────
    user = getattr(refresh_token, "user", None)
    if user is None or not getattr(user, "is_active", True):
        _LOGGER.warning("apply_profile: rejected token for inactive user from %s", remote)
        return _err(403, "User account is disabled")

    caller = getattr(user, "name", None) or getattr(user, "id", "unknown")

    # ── 6. Read body (enforce size at read time too) ───────────────────────
    try:
        body_bytes = await request.read()
    except Exception:
        return _err(400, "Failed to read request body")
    if len(body_bytes) > _MAX_BODY_BYTES:
        return _err(413, f"Request body too large (max {_MAX_BODY_BYTES} bytes)")

    # ── 7. Parse JSON ─────────────────────────────────────────────────────
    try:
        data = json.loads(body_bytes)
    except json.JSONDecodeError as exc:
        return _err(400, f"Invalid JSON: {exc}")
    if not isinstance(data, dict):
        return _err(400, "Request body must be a JSON object")

    # ── 8. Validate device_id ─────────────────────────────────────────────
    device_id = data.get("device_id") or ""
    if not isinstance(device_id, str) or not _DEVICE_ID_RE.match(device_id):
        return _err(
            400,
            "Invalid device_id: 1–64 chars, alphanumeric/hyphens/underscores only",
        )

    # ── 9. Validate and sanitise profile ──────────────────────────────────
    try:
        profile = _sanitise_profile(data.get("profile"))
    except ValueError as exc:
        return _err(400, str(exc))

    # ── 10. Resolve entry + bridge ────────────────────────────────────────
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        _LOGGER.error("apply_profile: no config entries found (integration not loaded)")
        return _err(503, "Integration not loaded")
    entry = entries[0]
    domain_data = hass.data.get(DOMAIN, {})
    bridge = domain_data.get(entry.entry_id)

    # ── 11. Persist ───────────────────────────────────────────────────────
    try:
        helper = StorageHelper(hass, entry)
        await helper.async_init()
        profs = dict(helper.storage.get("profiles") or {})
        profs[device_id] = profile
        await helper.persist_profiles(profs)
    except Exception:
        _LOGGER.exception(
            "apply_profile: failed to persist for '%s' (user '%s')",
            device_id, caller,
        )
        return _err(500, "Failed to save profile")

    # ── 12. Republish to MQTT ─────────────────────────────────────────────
    if bridge is not None and hasattr(bridge, "schedule_republish_reload"):
        try:
            bridge.schedule_republish_reload("apply_profile")
        except Exception:
            _LOGGER.debug("apply_profile: republish skipped", exc_info=True)

    _LOGGER.info(
        "apply_profile: applied profile for '%s' (user '%s', ip %s)",
        device_id, caller, remote,
    )
    return web.Response(
        content_type="application/json",
        text=json.dumps({"status": "ok", "device_id": device_id}),
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def _entities_options_handler(request: web.Request) -> web.Response:
    """CORS preflight for the entities endpoint — no authentication required."""
    return web.Response(headers=_CORS_HEADERS_GET)


async def _entities_get_handler(request: web.Request) -> web.Response:
    """Return a sorted list of all entity IDs known to Home Assistant."""
    hass = request.app["hass"]
    remote = request.remote

    # ── API enabled check ─────────────────────────────────────────────────────
    api_until = hass.data.get(CONF_API_UNTIL_KEY, 0)
    if time.time() > api_until:
        return _err(403, "API access is disabled. Enable it in Integration Options → API Access.")

    # ── Local-network guard ───────────────────────────────────────────────────
    if not _is_local(remote):
        return _err(403, "This endpoint is only accessible on a local network")

    # ── Rate limit ────────────────────────────────────────────────────────────
    if not _allow_rate(hass, remote or ""):
        return _err(429, "Too many requests — please wait before retrying")

    # ── Bearer token auth ─────────────────────────────────────────────────────
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return _err(401, "Missing or malformed Authorization header")
    token_str = auth_header[7:].strip()
    if not token_str:
        return _err(401, "Empty Bearer token")

    refresh_token = hass.auth.async_validate_access_token(token_str)
    if refresh_token is None:
        return _err(401, "Invalid or expired token")

    user = getattr(refresh_token, "user", None)
    if user is None or not getattr(user, "is_active", True):
        return _err(403, "User account is disabled")

    # ── Collect entity IDs ────────────────────────────────────────────────────
    entity_ids = sorted(hass.states.async_entity_ids())

    return web.Response(
        content_type="application/json",
        text=json.dumps({"entities": entity_ids}),
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ── Registration ───────────────────────────────────────────────────────────────

def register_apply_profile_route(hass) -> None:
    """Add OPTIONS and POST routes directly to the aiohttp router.

    Using hass.http.app.router instead of register_view() / HomeAssistantView
    avoids the aiohttp_cors double-registration conflict: HomeAssistantView
    registers its own OPTIONS handler then HA calls allow_cors() which tries
    to add a second one, raising ValueError.  By registering raw routes we
    own the OPTIONS handler entirely and emit exactly the CORS headers we need.
    """
    router = hass.http.app.router
    router.add_route("OPTIONS", _VIEW_PATH,      _options_handler)
    router.add_route("POST",    _VIEW_PATH,      _post_handler)
    router.add_route("OPTIONS", _ENTITIES_PATH,  _entities_options_handler)
    router.add_route("GET",     _ENTITIES_PATH,  _entities_get_handler)
    _LOGGER.debug("routes registered at %s and %s", _VIEW_PATH, _ENTITIES_PATH)
