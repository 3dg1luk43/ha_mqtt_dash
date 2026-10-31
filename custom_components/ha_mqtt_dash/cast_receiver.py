"""Cast from the YouTube app to a panel: a YouTube "TV" receiver per panel.

Port of the receiver side of yt-cast-receiver 2.1.0 (Node). DIAL discovery
(SSDP M-SEARCH answers, a device description and /apps/YouTube) makes the
YouTube app list the panel under Cast; the launch hands over a pairing code
that links the phone to the panel's "lounge" on youtube.com, and the commands
then arrive over YouTube's lounge protocol (a BrowserChannel long-poll on
/api/lounge/bc/bind). Playback goes to the panel's video player
(video_relay.PanelVideo). The sender's queue is kept (setPlaylist /
updatePlaylist / next / previous); there is no "up next" autoplay.

The core (``ChunkReader``, ``BindParams``, ``LoungeSession``,
``YouTubeReceiver``, ``SsdpResponder``) has no Home Assistant dependencies so
it can be tested standalone.
"""
from __future__ import annotations

import asyncio
import codecs
import json
import logging
import random
import secrets
import socket
import time
import uuid
from dataclasses import dataclass
from email.utils import formatdate
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from xml.sax.saxutils import escape

import aiohttp
from aiohttp import web
from yarl import URL

_LOGGER = logging.getLogger(__name__)

LOUNGE = "https://www.youtube.com/api/lounge"
URL_SCREEN_ID = f"{LOUNGE}/pairing/generate_screen_id"
URL_LOUNGE_TOKEN = f"{LOUNGE}/pairing/get_lounge_token_batch"
URL_REGISTER_PAIRING = f"{LOUNGE}/pairing/register_pairing_code"
URL_BIND = f"{LOUNGE}/bc/bind"

# Player states as the senders know them
IDLE, PLAYING, PAUSED, LOADING, STOPPED = -1, 1, 2, 3, 4
ACTIVE = (PLAYING, PAUSED, LOADING)

_TIMEOUT = aiohttp.ClientTimeout(total=20)
# The long-poll stays open for minutes; a silent one is reopened
_POLL_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=120)
_TOKEN_REFRESH_S = 1123200  # 13 days, when YouTube doesn't say


class LoungeError(Exception):
    pass


# ── Lounge messages ─────────────────────────────────────────────────────────

@dataclass
class Message:
    aid: Optional[int]
    name: str
    payload: Any = None


def _message(item: Any) -> Optional[Message]:
    """[aid, [name, *args]] → Message; one arg is the payload, several a list."""
    if not (isinstance(item, list) and len(item) == 2 and isinstance(item[1], list) and item[1]):
        return None
    aid, (name, *args) = item
    if not isinstance(name, str):
        return None
    return Message(aid if isinstance(aid, int) else None, name, args[0] if len(args) == 1 else (args or None))


class ChunkReader:
    """Incremental parser for bind responses: "<length>\\n<JSON array>" chunks.

    The length isn't used to slice (JS string length vs bytes vs code points):
    each chunk is read as one JSON value once enough text is there."""

    _json = json.JSONDecoder()

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")("replace")
        self._buf = ""

    def feed(self, data: bytes) -> List[Message]:
        self._buf += self._utf8.decode(data)
        out: List[Message] = []
        while True:
            buf = self._buf.lstrip()
            head, nl, rest = buf.partition("\n")
            if not nl:
                self._buf = buf
                return out
            if not head.strip().isdigit():
                self._buf = rest   # not a length line: resync on the next one
                continue
            body = rest.lstrip()
            try:
                value, end = self._json.raw_decode(body)
            except ValueError:
                if len(body) < int(head):
                    self._buf = buf   # incomplete: wait for more
                    return out
                self._buf = rest      # complete but malformed: skip it
                continue
            self._buf = body[end:]
            if isinstance(value, list):
                out += [m for m in map(_message, value) if m]


def parse_messages(body: bytes) -> List[Message]:
    return ChunkReader().feed(body)


def _form_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def _num(v: Any) -> float:
    try:
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 0.0


# ── Bind parameters ─────────────────────────────────────────────────────────

_DEVICE_INFO = {
    "year": 0, "os": "Windows", "osVersion": "10.0", "chipset": "", "clientName": "TVHTML5",
    "dialAdditionalDataSupportLevel": "unsupported", "mdxDialServerType": "MDX_DIAL_SERVER_TYPE_UNKNOWN",
}


class BindParams:
    """Query strings for the bind URL: starting a session, sending, the long-poll."""

    def __init__(self, device_id: str, screen_name: str, *, app: str = "ytcr", theme: str = "cl",
                 brand: str = "Apple", model: str = "iPad") -> None:
        self.id, self.name, self.app, self.theme = device_id, screen_name, app, theme
        self.device_info = json.dumps({**_DEVICE_INFO, "brand": brand, "model": model}, separators=(",", ":"))
        self.lounge_token: Optional[str] = None
        self.reset()

    def reset(self) -> None:
        self.sid: Optional[str] = None
        self.gsessionid: Optional[str] = None
        self.rid = random.randint(41000, 49999)
        self.aid = 3

    def update(self, msg: Message) -> None:
        if msg.name == "c" and isinstance(msg.payload, list) and msg.payload:
            self.sid = msg.payload[0]
        elif msg.name == "S" and isinstance(msg.payload, str):
            self.gsessionid = msg.payload
        if msg.aid:
            self.aid = max(self.aid, msg.aid)

    def query(self, kind: str, aid: Optional[int] = None) -> Dict[str, Any]:
        """kind: "init" (new session), "send" or "rpc" (the long-poll)."""
        need = {"loungeIdToken": self.lounge_token}
        if kind in ("send", "rpc"):
            need.update(SID=self.sid, gsessionid=self.gsessionid)
        missing = [k for k, v in need.items() if not v]
        if missing:
            raise LoungeError(f"bind params missing: {', '.join(missing)}")
        q: Dict[str, Any] = {
            "device": "LOUNGE_SCREEN", "id": self.id, "obfuscatedGaiaId": "", "name": self.name, "app": self.app,
            "theme": self.theme, "capabilities": "dsp,mic,dpa,ntb", "cst": "m", "mdxVersion": 2,
            "loungeIdToken": self.lounge_token, "VER": 8, "v": 2, "zx": secrets.token_hex(6), "t": 1,
        }
        if kind == "init":
            q.update(deviceInfo=self.device_info, RID=self.rid, CVER=1)
            self.rid += 1
        elif kind == "send":
            self.aid = max(aid, self.aid) if aid else self.aid
            q.update(deviceInfo=self.device_info, SID=self.sid, RID=self.rid, AID=self.aid, gsessionid=self.gsessionid)
            if not aid:
                self.aid += 1
            self.rid += 1
        elif kind == "rpc":
            q.update(RID="rpc", SID=self.sid, CI=0, AID=self.aid, gsessionid=self.gsessionid, TYPE="xmlhttp")
        return q


def bind_url(query: Dict[str, Any]) -> URL:
    return URL(f"{URL_BIND}?{urlencode(query, quote_via=quote)}", encoded=True)


# ── Lounge session ──────────────────────────────────────────────────────────

class LoungeSession:
    """A screen's link to YouTube: screen id → lounge token → bind session, then
    the long-poll, renewed on expiry. Incoming messages go to
    ``on_messages(messages, initial)``; ``on_ids()`` fires once the ids are known."""

    def __init__(self, params: BindParams, *, http: Optional[aiohttp.ClientSession] = None,
                 screen_id: Optional[str] = None, on_messages: Optional[Callable] = None,
                 on_ids: Optional[Callable[[], None]] = None) -> None:
        self.params, self.http, self.screen_id = params, http, screen_id
        self._stored_id = bool(screen_id)
        self.on_messages = on_messages
        self.on_ids = on_ids
        self.ready = False
        self.ofs = 0
        self.refresh_at = 0.0
        self._own_http = False
        self._restart = False
        self._poll: Optional[aiohttp.ClientResponse] = None
        self._send_lock = asyncio.Lock()

    def _session(self) -> aiohttp.ClientSession:
        if self.http is None or (self._own_http and self.http.closed):
            self.http, self._own_http = aiohttp.ClientSession(), True
        elif self.http.closed:   # HA's shared session: closed at shutdown
            raise LoungeError("HTTP session closed")
        return self.http

    async def close(self) -> None:
        if self._own_http and self.http:
            await self.http.close()

    async def _new_screen_id(self) -> str:
        async with self._session().get(URL_SCREEN_ID, timeout=_TIMEOUT) as r:
            r.raise_for_status()
            sid = (await r.text()).strip()
        if not sid or len(sid) > 200:
            raise LoungeError("no screen id")
        return sid

    async def _lounge_token(self) -> Dict[str, Any]:
        async with self._session().post(URL_LOUNGE_TOKEN, data={"screen_ids": self.screen_id}, timeout=_TIMEOUT) as r:
            r.raise_for_status()
            screens = (await r.json(content_type=None) or {}).get("screens") or []
        if not screens or not screens[0].get("loungeToken"):
            raise LoungeError("no lounge token")
        return screens[0]

    async def begin(self) -> None:
        self.ready, self._restart, self.ofs = False, False, 0
        self.params.reset()
        if not self.screen_id:
            self.screen_id, self._stored_id = await self._new_screen_id(), False
        try:
            token = await self._lounge_token()
        except (aiohttp.ClientError, LoungeError):
            if not self._stored_id:
                raise
            _LOGGER.info("youtube cast (%s): stored screen id rejected, pairing anew", self.params.name)
            self.screen_id, self._stored_id = await self._new_screen_id(), False
            token = await self._lounge_token()
        self.params.lounge_token = token["loungeToken"]
        self.refresh_at = time.monotonic() + (_num(token.get("refreshIntervalInMillis")) / 1000 or _TOKEN_REFRESH_S)
        if self.on_ids:
            self.on_ids()
        async with self._session().post(bind_url(self.params.query("init")), data={"count": "0"}, timeout=_TIMEOUT) as r:
            r.raise_for_status()
            msgs = parse_messages(await r.read())
        for m in msgs:
            self.params.update(m)
        self.params.query("rpc")   # raises without SID / gsessionid
        self.ready = True
        if self.on_messages:
            await self.on_messages([m for m in msgs if m.name == "loungeStatus"], True)

    async def run(self) -> None:
        """Keep the session up: (re)start it, follow the long-poll, back off on errors."""
        delay = 5
        while True:
            started = time.monotonic()
            try:
                await self.begin()
                await self._listen()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # network, YouTube API changes
                _LOGGER.warning("youtube cast (%s): lounge session failed (%s), retrying in %ss",
                                self.params.name, err or type(err).__name__, delay)
            else:
                if time.monotonic() - started > 60:   # renewed after a normal run
                    delay = 5
                    continue
            self.ready = False
            await asyncio.sleep(delay)
            delay = min(delay * 2, 300)

    async def _listen(self) -> None:
        failures = 0
        while not self._restart and time.monotonic() < self.refresh_at:
            try:
                async with self._session().get(bind_url(self.params.query("rpc")), timeout=_POLL_TIMEOUT) as r:
                    if r.status in (400, 404, 410):   # unknown / expired SID
                        _LOGGER.debug("youtube cast (%s): session ended (HTTP %s)", self.params.name, r.status)
                        return
                    r.raise_for_status()
                    self._poll, failures = r, 0
                    reader = ChunkReader()
                    async for data in r.content.iter_any():
                        msgs = [m for m in reader.feed(data) if m.name != "noop"]
                        for m in msgs:
                            self.params.update(m)
                        msgs = [m for m in msgs if m.name not in ("c", "S")]
                        if msgs and self.on_messages:
                            await self.on_messages(msgs, False)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                if self._restart:
                    return
                failures += 1
                if failures > 3:
                    raise LoungeError(f"long-poll failed: {err or type(err).__name__}") from err
                await asyncio.sleep(failures)
            finally:
                self._poll = None

    def restart(self) -> None:
        """Start a new bind session (e.g. after YouTube rejected a send)."""
        self._restart = True
        if self._poll is not None:
            self._poll.close()

    async def send(self, messages: List[Message]) -> bool:
        if not messages:
            return True
        async with self._send_lock:
            try:
                url = bind_url(self.params.query("send", messages[0].aid))
            except LoungeError:
                return False   # no session right now; senders re-sync on connect
            form = {"count": str(len(messages)), "ofs": str(self.ofs)}
            for i, m in enumerate(messages):
                form[f"req{i}__sc"] = m.name
                for k, v in (m.payload or {}).items():
                    if v is not None:
                        form[f"req{i}_{k}"] = _form_value(v)
            self.ofs += len(messages)
            try:
                async with self._session().post(url, data=form, timeout=_TIMEOUT) as r:
                    status = r.status
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.debug("youtube cast (%s): send failed: %s", self.params.name, err)
                return False
        if status < 300:
            return True
        _LOGGER.debug("youtube cast (%s): send %s: HTTP %s", self.params.name, [m.name for m in messages], status)
        if status in (400, 404, 410):
            self.restart()
        return False

    async def register_pairing_code(self, code: str) -> None:
        if not self.screen_id:
            raise LoungeError("no screen id yet")
        data = {"access_type": "permanent", "app": self.params.app, "pairing_code": code,
                "screen_id": self.screen_id, "screen_name": self.params.name, "device_id": self.params.id}
        async with self._session().post(URL_REGISTER_PAIRING, data=data, timeout=_TIMEOUT) as r:
            r.raise_for_status()


# ── Receiver (YouTube app + player state) ──────────────────────────────────

class YouTubeReceiver:
    """One cast target: the lounge session, the sender's queue and the player
    state the senders see, mapped onto ``player`` (async play(video_id, start) /
    pause / resume / seek(position) / stop, and snapshot() → {"state":
    playing|paused|loading|None, "position", "position_at", "duration", "video",
    "end"}). Also answers DIAL requests under ``base_url``."""

    brand, model = "Apple", "iPad"

    def __init__(self, name: str, player, *, base_url: str, uuid_: Optional[str] = None,
                 screen_id: Optional[str] = None, device_id: Optional[str] = None,
                 http: Optional[aiohttp.ClientSession] = None,
                 on_ids: Optional[Callable[[Dict[str, str]], None]] = None) -> None:
        self.name, self.player, self.base_url = name, player, base_url.rstrip("/")
        self.uuid = uuid_ or str(uuid.uuid4())
        self.params = BindParams(device_id or str(uuid.uuid4()), f"YouTube on {name}", brand=self.brand, model=self.model)
        self.lounge = LoungeSession(self.params, http=http, screen_id=screen_id, on_messages=self._incoming,
                                    on_ids=(lambda: on_ids(self.ids())) if on_ids else None)
        self.list_id: Optional[str] = None
        self.video_ids: List[str] = []
        self.current: Optional[Dict[str, Any]] = None   # {"id", "index", ["ctt", "params"]}
        self.status = IDLE
        self.volume = {"level": 100, "muted": False}
        self.cpn = secrets.token_hex(8)
        self.senders: Dict[str, Dict[str, Any]] = {}
        self._implicit: set = set()          # senders that dropped without "disconnect"
        self._last: Optional[Dict[str, Any]] = None   # last state told to the senders
        self._hint: Optional[Tuple[float, float]] = None   # (position, at) until the panel reports
        self._seen: Optional[str] = None     # the panel's last state, for its own changes
        self._busy = 0
        self._inbox: Optional[asyncio.Queue] = None
        self._tasks: List[asyncio.Task] = []

    @property
    def location(self) -> str:
        return f"{self.base_url}/ssdp/device-desc.xml"

    def ids(self) -> Dict[str, str]:
        return {"uuid": self.uuid, "screen_id": self.lounge.screen_id or "", "device_id": self.params.id}

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._inbox = asyncio.Queue()
        self._tasks = [loop.create_task(self.lounge.run()), loop.create_task(self._work())]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks = []
        if self.lounge.ready:
            try:
                await asyncio.wait_for(self.lounge.send([Message(None, "loungeScreenDisconnected", {})]), 5)
            except Exception:
                pass
        self.lounge.ready = False
        await self.lounge.close()

    async def _incoming(self, messages: List[Message], initial: bool) -> None:
        if self._inbox is not None:
            self._inbox.put_nowait((messages, initial))
        else:  # not started (tests)
            for m in messages:
                await self.handle(m, initial)

    async def _work(self) -> None:
        while True:
            messages, initial = await self._inbox.get()
            for m in messages:
                try:
                    await self.handle(m, initial)
                except Exception:
                    _LOGGER.exception("youtube cast (%s): handling %s failed", self.name, m.name)

    def panel_changed(self) -> None:
        """The panel's video changed in HA (ended, closed, paused on the panel…)."""
        if not self._busy and self._inbox is not None:
            self._inbox.put_nowait(([Message(None, "_panel")], False))

    # ── incoming messages (YouTubeApp) ──

    async def handle(self, msg: Message, initial: bool = False) -> None:
        aid, name = msg.aid, msg.name
        p = msg.payload if isinstance(msg.payload, dict) else {}
        out: List[Message] = []
        if name == "getNowPlaying":
            out.append(self._now_playing(aid))
        elif name == "loungeStatus":
            out += await self._lounge_status(aid, p, initial)
        elif name in ("setPlaylist", "updatePlaylist"):
            out += await self._set_playlist(aid, name, p)
        elif name == "addVideo" and p.get("videoId"):
            if p["videoId"] not in self.video_ids:
                self.video_ids.append(p["videoId"])
            out += [self._now_playing(aid), self._nav(aid)]
        elif name == "next":
            await self._step(+1, aid)
        elif name == "previous":
            await self._step(-1, aid)
        elif name == "pause":
            await self.pause(aid)
        elif name == "play":
            await self.resume(aid)
        elif name == "stopVideo":
            await self.stop_video(aid)
        elif name == "seekTo":
            await self.seek(_num(p.get("newTime")), aid)
        elif name == "getVolume":
            out.append(self._volume(aid))
        elif name == "setVolume":
            muted = p.get("muted")
            self.volume = {"level": int(min(100, _num(p.get("volume", self.volume["level"])))),
                           "muted": muted is True or str(muted).strip().lower() == "true"}
            out.append(self._volume(aid))
        elif name == "setAutoplayMode":
            out.append(self._autoplay(aid))
        elif name == "_panel":
            await self._panel()
        else:
            _LOGGER.debug("youtube cast (%s): not handled: %s", self.name, name)
        if out:
            await self.lounge.send(out)

    async def _lounge_status(self, aid, p: Dict[str, Any], initial: bool) -> List[Message]:
        try:
            devices = json.loads(p.get("devices") or "[]")
        except ValueError:
            devices = []
        remotes = {d["id"]: d for d in devices if isinstance(d, dict) and d.get("type") == "REMOTE_CONTROL"
                   and d.get("id") and (d.get("name") or d.get("clientName"))}
        if initial:   # (re)started session: whoever is still in the lounge
            self.senders = remotes
            return [self._autoplay(aid), self._nav(aid), self._now_playing(aid)] if remotes else []
        try:
            event = json.loads(p.get("connectionEventDetails") or "null")
        except ValueError:
            event = None
        dev = event.get("deviceId") if isinstance(event, dict) else None
        if dev and dev in remotes:
            if dev in self.senders:
                return []
            self.senders[dev] = remotes[dev]
            self._implicit.discard(dev)
            _LOGGER.info("youtube cast (%s): %s connected", self.name, remotes[dev].get("name") or remotes[dev].get("clientName"))
            state = self._state()
            return [self._autoplay(aid), self._nav(aid), self._now_playing(aid, state), self._on_state_change(aid, state)]
        if dev and dev in self.senders:
            sender = self.senders.pop(dev)
            implicit = str(event.get("ui")).lower() != "true"
            if implicit:
                self._implicit.add(dev)
            _LOGGER.info("youtube cast (%s): %s disconnected%s", self.name,
                         sender.get("name") or sender.get("clientName"), " (dropped)" if implicit else "")
            # Like a TV: keep playing when a phone just drops; stop once the last one disconnects
            if not self.senders and not self._implicit:
                await self.reset(aid)
            return []
        return [self._nav(aid), self._autoplay(aid)]

    async def _set_playlist(self, aid, name: str, p: Dict[str, Any]) -> List[Message]:
        before = (self.current or {}).get("id"), (self.current or {}).get("index")
        nav_before = self._has_prev_next()
        if not p.get("listId"):
            self.list_id, self.video_ids, self.current = None, [], None
        else:
            self.list_id = p["listId"]
            self.video_ids = [v for v in str(p.get("videoIds") or "").split(",") if v]
            if name == "setPlaylist":
                self.current = None
                if p.get("videoId") and str(p.get("currentIndex", "")).isdigit():
                    self.current = {"id": p["videoId"], "index": int(p["currentIndex"]),
                                    **{k: p[k] for k in ("ctt", "params") if p.get(k)}}
            elif self.current and self.current["id"] in self.video_ids:
                self.current = {**{k: v for k, v in self.current.items() if k != "params"},
                                "index": self.video_ids.index(self.current["id"]),
                                **({"params": p["params"]} if p.get("params") else {})}
            else:
                self.current = None
        after = (self.current or {}).get("id"), (self.current or {}).get("index")
        if name == "setPlaylist" and (before != after or self.status in (IDLE, STOPPED)):
            if self.current:
                await self.play(self.current, _num(p.get("currentTime")), aid)
            else:
                await self.stop_video(aid)
            return []
        if name == "updatePlaylist" and not self.current:
            await self.stop_video(aid)
            return []
        out = [self._now_playing(aid)]
        if self._has_prev_next() != nav_before:
            out.append(self._nav(aid))
        return out

    async def _step(self, delta: int, aid=None) -> None:
        i = (self.current or {}).get("index")
        j = i + delta if isinstance(i, int) else -1
        if 0 <= j < len(self.video_ids):
            await self.play({"id": self.video_ids[j], "index": j}, 0.0, aid)
        else:
            await self.stop_video(aid)

    async def _panel(self) -> None:
        """React to the panel's own changes: paused / resumed there, ended, closed."""
        snap = self._snapshot()
        state = snap.get("state")
        prev, self._seen = self._seen, state
        if self.status not in ACTIVE:
            return
        if state in ("playing", "paused") and state != prev:
            new = PLAYING if state == "playing" else PAUSED
            if new != self.status:
                await self._set_status(new)
        elif state is None and prev is not None:
            if snap.get("end") == "ended" and self._has_prev_next()[1]:
                await self._step(+1)   # next in the sender's queue
            else:
                await self._set_status(STOPPED)
        elif state == "playing" and self.status == PLAYING and self._last:
            # resync the senders' progress bar after a stall or a seek on the panel
            expected = self._last["position"] + time.time() - self._last["at"]
            if abs(self.position() - expected) > 5:
                await self._set_status(PLAYING)

    # ── player (Player.js) ──

    async def _call(self, fn, *args) -> bool:
        self._busy += 1
        try:
            await fn(*args)
            return True
        except Exception as err:
            _LOGGER.warning("youtube cast (%s): %s failed: %s", self.name, getattr(fn, "__name__", fn), err)
            return False
        finally:
            self._busy -= 1
            self._seen = self._snapshot().get("state")

    async def play(self, video: Dict[str, Any], position: float = 0.0, aid=None) -> bool:
        _LOGGER.info("youtube cast (%s): play %s from %.0fs", self.name, video["id"], position)
        self.current = video
        self._hint = (position, time.time())
        await self._set_status(LOADING, aid)
        ok = await self._call(self.player.play, video["id"], position)
        self._hint = (position, time.time())
        await self._set_status(PLAYING if ok else STOPPED, aid)
        return ok

    async def pause(self, aid=None) -> bool:
        if self.status != PLAYING:
            return False
        pos = self.position()
        if not await self._call(self.player.pause):
            return False
        self._hint = (pos, time.time())
        await self._set_status(PAUSED, aid)
        return True

    async def resume(self, aid=None) -> bool:
        if self.status == PLAYING:
            await self._set_status(PLAYING, aid)
            return False
        if self.status == PAUSED:
            pos = self.position()
            if not await self._call(self.player.resume):
                return False
            self._hint = (pos, time.time())
            await self._set_status(PLAYING, aid)
            return True
        if self.current:
            return await self.play(self.current, 0.0, aid)
        return False

    async def stop_video(self, aid=None) -> bool:
        if self.status in (STOPPED, IDLE):
            return True
        if not await self._call(self.player.stop):
            return False
        await self._set_status(STOPPED, aid)
        return True

    async def seek(self, position: float, aid=None) -> bool:
        if self.status not in (PLAYING, PAUSED):
            return False
        was = self.status
        before = self._state()
        fake = {**before, "status": LOADING, "position": position}
        await self._emit(fake, before, aid)
        if not await self._call(self.player.seek, position):
            return False
        self._hint, self._last = (position, time.time()), fake
        if was == PAUSED:   # as yt-cast-receiver: a seek resumes
            return await self.resume(aid)
        await self._set_status(PLAYING, aid)
        return True

    async def reset(self, aid=None) -> None:
        self.list_id, self.video_ids = None, []
        await self.stop_video(aid)
        self.current, self._last, self.status = None, None, IDLE

    def _snapshot(self) -> Dict[str, Any]:
        """The panel's video state, empty unless it is the current video."""
        snap = self.player.snapshot() or {}
        return snap if self.current and snap.get("video") == self.current["id"] else {"end": snap.get("end")}

    def position(self) -> float:
        snap = self._snapshot()
        pos, at = snap.get("position"), snap.get("position_at")
        if self._hint and (not at or self._hint[1] >= at):
            pos, at = self._hint
        pos = _num(pos)
        if self.status == PLAYING and at:
            pos += max(0.0, time.time() - at)
        dur = self.duration()
        return round(min(pos, dur) if dur else pos, 3)

    def duration(self) -> float:
        return round(_num(self._snapshot().get("duration")), 3)

    def _state(self) -> Dict[str, Any]:
        cur = self.current or {}
        return {"status": self.status, "position": self.position(), "duration": self.duration(), "at": time.time(),
                "video": cur.get("id"), "list": self.list_id, "index": cur.get("index"),
                "volume": (self.volume["level"], self.volume["muted"])}

    async def _set_status(self, status: int, aid=None) -> None:
        self.status = status
        cur = self._state()
        prev, self._last = self._last, cur
        await self._emit(cur, prev, aid)

    async def _emit(self, cur: Dict[str, Any], prev: Optional[Dict[str, Any]], aid=None) -> None:
        """What changed → messages to the senders (YouTubeApp's player state handler)."""
        if not self.senders:
            return
        status_changed = not prev or prev["status"] != cur["status"]
        out: List[Message] = []
        if status_changed or prev["position"] != cur["position"]:
            out.append(self._on_state_change(aid, cur))
        now_changed = not prev or any(prev[k] != cur[k] for k in ("video", "list", "index"))
        if now_changed or (status_changed and (not prev or prev["status"] != PLAYING)):
            out += [self._now_playing(aid, cur), self._nav(aid)]
        if not prev or prev["volume"] != cur["volume"]:
            out.append(self._volume(aid))
        await self.lounge.send(out)

    # ── outgoing messages (Message.js) ──

    def _has_prev_next(self) -> Tuple[bool, bool]:
        i = (self.current or {}).get("index")
        if not isinstance(i, int):
            return False, False
        return 0 < i <= len(self.video_ids), i + 1 < len(self.video_ids)

    def _nav(self, aid) -> Message:
        prev, nxt = self._has_prev_next()
        return Message(aid, "onHasPreviousNextChanged", {"hasPrevious": prev, "hasNext": nxt})

    def _autoplay(self, aid) -> Message:
        return Message(aid, "onAutoplayModeChanged", {"autoplayMode": "UNSUPPORTED"})

    def _volume(self, aid) -> Message:
        return Message(aid, "onVolumeChanged", {"volume": self.volume["level"], "muted": self.volume["muted"]})

    def _on_state_change(self, aid, s: Dict[str, Any]) -> Message:
        return Message(aid, "onStateChange", {
            "state": s["status"], "currentTime": s["position"], "duration": s["duration"],
            "loadedTime": s["duration"] if s["status"] in ACTIVE else 0,
            "seekableStartTime": 0, "seekableEndTime": s["duration"], "cpn": self.cpn})

    def _now_playing(self, aid, s: Optional[Dict[str, Any]] = None) -> Message:
        s = s or self._state()
        if not s["video"]:
            return Message(aid, "nowPlaying", {})
        p: Dict[str, Any] = {
            "currentTime": s["position"], "duration": s["duration"], "cpn": self.cpn,
            "loadedTime": s["duration"] if s["status"] in ACTIVE else 0, "videoId": s["video"], "state": s["status"],
            "seekableStartTime": 0, "seekableEndTime": s["duration"]}
        if s["list"]:
            p["listId"] = s["list"]
        if s["index"] is not None:
            p["currentIndex"] = s["index"]
        p.update({k: v for k, v in (self.current or {}).items() if k in ("ctt", "params")})
        return Message(aid, "nowPlaying", p)

    # ── DIAL (peer-dial) ──

    def device_xml(self) -> str:
        return (
            '<?xml version="1.0"?>\n<root xmlns="urn:schemas-upnp-org:device-1-0">\n'
            "  <specVersion><major>1</major><minor>0</minor></specVersion>\n"
            f"  <URLBase>{escape(self.base_url)}</URLBase>\n  <device>\n"
            f"    <deviceType>{DIAL_DEVICE}</deviceType>\n"
            f"    <friendlyName>{escape(self.name)}</friendlyName>\n"
            f"    <manufacturer>{escape(self.brand)}</manufacturer>\n"
            f"    <modelName>{escape(self.model)}</modelName>\n"
            f"    <UDN>uuid:{self.uuid}</UDN>\n"
            "    <serviceList><service>\n"
            f"      <serviceType>{DIAL_ST}</serviceType>\n"
            "      <serviceId>urn:dial-multiscreen-org:serviceId:dial</serviceId>\n"
            "      <controlURL>/ssdp/notfound</controlURL><eventSubURL>/ssdp/notfound</eventSubURL>"
            "<SCPDURL>/ssdp/notfound</SCPDURL>\n"
            "    </service></serviceList>\n  </device>\n</root>\n")

    def app_xml(self) -> str:
        state = "running" if self.lounge.ready else "stopped"
        link = '\n  <link rel="run" href="run"/>' if self.lounge.ready else ""
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<service xmlns="urn:dial-multiscreen-org:schemas:dial" dialVer="1.7">\n'
                f'  <name>YouTube</name>\n  <options allowStop="false"/>\n  <state>{state}</state>{link}\n</service>\n')

    async def dial(self, request: web.Request, path: str) -> web.StreamResponse:
        """DIAL under ``base_url``: ssdp/device-desc.xml, apps, apps/YouTube[/run]."""
        method = request.method
        if path == "ssdp/device-desc.xml" and method == "GET":
            return web.Response(text=self.device_xml(), content_type="application/xml",
                                headers={"Application-URL": f"{self.base_url}/apps"})
        if path == "apps" and method == "GET":
            return web.Response(status=204)
        if path == "apps/YouTube" and method == "GET":
            return web.Response(text=self.app_xml(), content_type="application/xml")
        if path.startswith("apps/YouTube") and method in ("POST", "DELETE") and not _origin_ok(request.headers.get("Origin")):
            return web.Response(status=403)
        if path == "apps/YouTube" and method == "POST":
            return await self._launch(request)
        if path == "apps/YouTube/dial_data" and method == "POST":
            return web.Response(status=501)
        if path.startswith("apps/YouTube/") and method == "DELETE":
            return web.Response(status=405)   # allowStop: false
        return web.Response(status=404)

    async def _launch(self, request: web.Request) -> web.StreamResponse:
        if (request.content_length or 0) > 4096:
            return web.Response(status=413)
        data = parse_qs(await request.text())
        code, theme = (data.get("pairingCode") or [""])[0], (data.get("theme") or ["cl"])[0]
        if not self.lounge.ready:
            return web.Response(status=503)
        if code and theme == "cl":   # "m" is YouTube Music: not offered
            try:
                await self.lounge.register_pairing_code(code)
            except Exception as err:
                _LOGGER.warning("youtube cast (%s): pairing failed: %s", self.name, err)
                return web.Response(status=503)
            _LOGGER.debug("youtube cast (%s): sender paired over DIAL", self.name)
        return web.Response(status=200, headers={"Location": f"{self.base_url}/apps/YouTube/run"})


def _origin_ok(origin: Optional[str]) -> bool:
    """Web pages on the LAN may not launch (DIAL CSRF rule); apps and YouTube may."""
    if not origin:
        return True
    o = origin.strip().lower()
    if not o.startswith(("http:", "https:", "file:")):
        return True   # package:com.google.android.youtube …
    host = urlsplit(o).hostname or ""
    return o.startswith("https:") and (host == "youtube.com" or host.endswith(".youtube.com"))


# ── SSDP (peer-ssdp) ────────────────────────────────────────────────────────

SSDP_ADDR, SSDP_PORT = "239.255.255.250", 1900
DIAL_ST = "urn:dial-multiscreen-org:service:dial:1"
DIAL_DEVICE = "urn:dial-multiscreen-org:device:dial:1"
SERVER = "Linux UPnP/1.1 ha_mqtt_dash/1.0"


@dataclass
class SsdpTarget:
    uuid: str
    location: str


def _ssdp(start: str, headers: Dict[str, str]) -> bytes:
    return (start + "\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n").encode()


def parse_ssdp(data: bytes) -> Tuple[str, Dict[str, str]]:
    lines = data.decode("utf-8", "replace").split("\r\n")
    headers = {}
    for line in lines[1:]:
        k, sep, v = line.partition(":")
        if sep:
            headers[k.strip().upper()] = v.strip()
    return lines[0].split(" ")[0].upper(), headers


def msearch_replies(data: bytes, targets: List[SsdpTarget]) -> List[bytes]:
    """Answers to an M-SEARCH for DIAL (only: HA's own discovery searches ssdp:all)."""
    method, h = parse_ssdp(data)
    st = h.get("ST", "")
    if method != "M-SEARCH":
        return []
    out = []
    for t in targets:
        if st in (DIAL_ST, DIAL_DEVICE) or st == f"uuid:{t.uuid}":
            out.append(_ssdp("HTTP/1.1 200 OK", {
                "CACHE-CONTROL": "max-age=1800", "DATE": formatdate(usegmt=True), "EXT": "",
                "LOCATION": t.location, "SERVER": SERVER, "ST": st,
                "USN": f"uuid:{t.uuid}" if st.startswith("uuid:") else f"uuid:{t.uuid}::{st}",
                "BOOTID.UPNP.ORG": "7337", "CONFIGID.UPNP.ORG": "7337"}))
    return out


def notify(t: SsdpTarget, alive: bool = True) -> List[bytes]:
    out = []
    for nt in (DIAL_DEVICE, DIAL_ST):
        h = {"HOST": f"{SSDP_ADDR}:{SSDP_PORT}", "NT": nt, "NTS": "ssdp:alive" if alive else "ssdp:byebye",
             "USN": f"uuid:{t.uuid}::{nt}", "BOOTID.UPNP.ORG": "7337", "CONFIGID.UPNP.ORG": "7337"}
        if alive:
            h.update({"CACHE-CONTROL": "max-age=1800", "LOCATION": t.location, "SERVER": SERVER})
        out.append(_ssdp("NOTIFY * HTTP/1.1", h))
    return out


def _listen_socket(iface: Optional[str]) -> socket.socket:
    """UDP 1900 shared with HA's own ssdp integration."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        try:
            s.bind((SSDP_ADDR, SSDP_PORT))   # multicast only: unicast to :1900 stays HA's
        except OSError:
            s.bind(("", SSDP_PORT))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                     socket.inet_aton(SSDP_ADDR) + socket.inet_aton(iface or "0.0.0.0"))
        s.setblocking(False)
    except OSError:
        s.close()
        raise
    return s


def _send_socket(iface: Optional[str]) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    if iface:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface))
    s.bind((iface or "", 0))
    s.setblocking(False)
    return s


class _Udp(asyncio.DatagramProtocol):
    def __init__(self, on_datagram: Callable[[bytes, Any], None]) -> None:
        self.on_datagram = on_datagram

    def datagram_received(self, data, addr) -> None:
        self.on_datagram(data, addr)


class SsdpResponder:
    """Answers DIAL M-SEARCHes for every receiver (unicast, from a separate
    socket), with NOTIFY alive on start / every 15 min and byebye on stop."""

    def __init__(self, targets: Callable[[], List[SsdpTarget]], iface: Optional[str] = None) -> None:
        self.targets = targets
        self.iface = iface if iface and not iface.startswith("127.") else None
        self._listen = self._send = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._send, _ = await loop.create_datagram_endpoint(lambda: _Udp(lambda *_: None), sock=_send_socket(self.iface))
        try:
            self._listen, _ = await loop.create_datagram_endpoint(lambda: _Udp(self._on_datagram),
                                                                  sock=_listen_socket(self.iface))
        except OSError:
            self._send.close()
            self._send = None
            raise
        self._task = loop.create_task(self._advertise())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self._send:
            self.announce(self.targets(), alive=False)
        for t in (self._listen, self._send):
            if t:
                t.close()
        self._listen = self._send = None

    def announce(self, targets: List[SsdpTarget], alive: bool = True) -> None:
        if not self._send:
            return
        for t in targets:
            for msg in notify(t, alive):
                self._send.sendto(msg, (SSDP_ADDR, SSDP_PORT))

    async def _advertise(self) -> None:
        while True:
            self.announce(self.targets())
            await asyncio.sleep(900)

    def _on_datagram(self, data: bytes, addr) -> None:
        if not data.startswith(b"M-SEARCH") or not self._send:
            return
        for reply in msearch_replies(data, self.targets()):
            self._send.sendto(reply, addr)


# ── Home Assistant glue ─────────────────────────────────────────────────────

def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def video_id_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    u = urlsplit(url)
    if not (u.hostname or "").endswith("youtube.com") or u.path != "/watch":
        return None
    return (parse_qs(u.query).get("v") or [None])[0]


def friendly_name(device_id: str) -> str:
    name = device_id.replace("_", " ").replace("-", " ").strip()
    return f"{name[:1].upper()}{name[1:]} iPad"


class PanelPlayer:
    """Receiver commands → the panel's video player (video_relay.PanelVideo)."""

    def __init__(self, video, device_id: str) -> None:
        self.video, self.device_id = video, device_id

    async def play(self, video_id: str, start: float) -> None:
        await self.video.async_play(self.device_id, watch_url(video_id), start=start)

    async def pause(self) -> None:
        await self.video.async_control(self.device_id, "pause")

    async def resume(self) -> None:
        await self.video.async_control(self.device_id, "play")

    async def seek(self, position: float) -> None:
        await self.video.async_control(self.device_id, "seek", position)

    async def stop(self) -> None:
        await self.video.async_stop(self.device_id)

    def snapshot(self) -> Dict[str, Any]:
        st = self.video.state(self.device_id)
        return {**st, "video": video_id_of(st.get("url")), "end": self.video.last_end.get(self.device_id)}


class PanelCast:
    """One YouTube receiver per panel (option "Allow casting from the YouTube
    app"), DIAL mounted on the video server (/dial/<panel>/…) and one SSDP
    responder for all of them."""

    def __init__(self, hass, bridge) -> None:
        self.hass, self.bridge = hass, bridge
        self.receivers: Dict[str, YouTubeReceiver] = {}
        self.ssdp: Optional[SsdpResponder] = None
        self._unsubs: List[Callable[[], None]] = []
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        from .const import CONF_YT_CAST
        return bool((self.bridge.entry.options or {}).get(CONF_YT_CAST, True))

    def _panels(self) -> List[str]:
        from .const import CONF_DEVICES
        from .mqtt_bridge import _valid_device_id
        return [d["device_id"] for d in (self.bridge.cfg.get(CONF_DEVICES) or [])
                if isinstance(d, dict) and _valid_device_id(d.get("device_id"))]

    async def async_setup(self) -> None:
        from homeassistant.core import callback  # type: ignore
        from homeassistant.helpers.dispatcher import async_dispatcher_connect  # type: ignore
        from .video_relay import SIGNAL_VIDEO_UPDATED

        from homeassistant.const import EVENT_HOMEASSISTANT_STOP  # type: ignore

        @callback
        def _video_changed(device_id: str) -> None:
            r = self.receivers.get(device_id)
            if r:
                r.panel_changed()

        async def _ha_stop(_event) -> None:   # phones see the panels leave
            self._unsubs = [u for u in self._unsubs if u is not unsub_stop]
            await self.async_unload()
        self._unsubs.append(async_dispatcher_connect(self.hass, SIGNAL_VIDEO_UPDATED, _video_changed))
        unsub_stop = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _ha_stop)
        self._unsubs.append(unsub_stop)
        await self.async_sync()

    async def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        async with self._lock:
            await self._stop_all()

    async def async_sync(self) -> None:
        """Start / stop receivers to match the option and the panel list."""
        async with self._lock:
            wanted = set(self._panels()) if self.enabled else set()
            for did in set(self.receivers) - wanted:
                r = self.receivers.pop(did)
                if self.ssdp:
                    self.ssdp.announce([SsdpTarget(r.uuid, r.location)], alive=False)
                await r.stop()
            if not wanted:
                await self._stop_all()
                return
            new = sorted(wanted - set(self.receivers))
            if not new:
                return
            try:
                server = await self.bridge.video._ensure_server()
            except OSError as err:
                _LOGGER.warning("youtube cast: video server port %s unavailable: %s", self.bridge.video.port, err)
                return
            ip = await self.bridge.video._source_ip()
            if ip.startswith("127."):
                _LOGGER.warning("youtube cast: no LAN address for Home Assistant (network integration), casting off")
                return
            server.mounts["dial"] = self._dial
            from homeassistant.helpers.aiohttp_client import async_get_clientsession  # type: ignore
            http = async_get_clientsession(self.hass)
            for did in new:
                st = self.bridge._storage_helper.get_cast(did)
                r = YouTubeReceiver(friendly_name(did), PanelPlayer(self.bridge.video, did),
                                    base_url=f"http://{ip}:{self.bridge.video.port}/dial/{did}",
                                    uuid_=st.get("uuid"), screen_id=st.get("screen_id") or None,
                                    device_id=st.get("device_id"), http=http,
                                    on_ids=lambda ids, did=did: self._save(did, ids))
                self.receivers[did] = r
                r.start()
                _LOGGER.info("youtube cast: %s listed as \"%s\" (%s)", did, r.name, r.location)
            if self.ssdp is None:
                self.ssdp = SsdpResponder(self._targets, ip)
                try:
                    await self.ssdp.start()
                except OSError as err:
                    _LOGGER.warning("youtube cast: SSDP (UDP 1900) unavailable, phones won't find the panels: %s", err)
                    self.ssdp = None
            else:
                self.ssdp.announce([SsdpTarget(self.receivers[d].uuid, self.receivers[d].location) for d in new])

    async def _stop_all(self) -> None:
        if self.ssdp:
            await self.ssdp.stop()
            self.ssdp = None
        for r in list(self.receivers.values()):
            await r.stop()
        self.receivers.clear()
        server = getattr(self.bridge.video, "server", None)
        if server:
            server.mounts.pop("dial", None)

    def _targets(self) -> List[SsdpTarget]:
        return [SsdpTarget(r.uuid, r.location) for r in self.receivers.values()]

    def _save(self, device_id: str, ids: Dict[str, str]) -> None:
        helper = self.bridge._storage_helper
        if helper.get_cast(device_id) != ids:
            self.hass.async_create_task(helper.async_set_cast(device_id, ids))

    async def _dial(self, request: web.Request) -> web.StreamResponse:
        did, _, path = request.match_info["path"].partition("/")
        r = self.receivers.get(did)
        if not r:
            raise web.HTTPNotFound()
        return await r.dial(request, path)
