"""Video for panels: any URL ffmpeg can read (YouTube via yt-dlp, files, HLS,
RTSP…) decoded here and served to the iPad as plain-HTTP MJPEG.

The iPad 1 can't reach YouTube itself (iOS 5 only speaks TLS 1.0) and can't
decode most modern streams, but it shows MJPEG natively. So this module
resolves the link, runs ffmpeg to produce small JPEG frames and serves them
from its own little HTTP server on the LAN (``/video/<token>.mjpeg``). No
audio: MJPEG carries none.

The core (``VideoStream``, ``resolve``, ``MjpegServer``) has no Home Assistant
dependencies so it can be tested standalone.
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

BOUNDARY = "mqttdashframe"
DIRECT_MEDIA = re.compile(r"\.(mp4|m4v|mov|mkv|webm|m3u8|mjpe?g|ts|avi)(\?|$)|^(rtsp|rtmp|udp|srt)://", re.I)


@dataclass
class Resolved:
    url: str
    title: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    duration: Optional[float] = None
    thumbnail: Optional[str] = None


def resolve(url: str, max_height: int = 480) -> Resolved:
    """Blocking: turn a page link (YouTube…) into a stream URL ffmpeg can open.
    Direct media URLs pass through. Run in an executor."""
    if DIRECT_MEDIA.search(url):
        return Resolved(url=url)
    try:
        import yt_dlp  # type: ignore
    except ImportError:
        _LOGGER.warning("yt-dlp is not installed; playing %s as a direct URL", url)
        return Resolved(url=url)
    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True,
        # Video only (MJPEG has no audio); H.264 first, it's the cheapest to decode
        "format": f"bv*[height<={max_height}][vcodec^=avc1]/bv*[height<={max_height}]/b[height<={max_height}]/bv*/b",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)
    fmt = (info.get("requested_formats") or [info])[0]
    return Resolved(
        url=fmt.get("url") or info["url"],
        title=info.get("title"),
        headers={k: v for k, v in (fmt.get("http_headers") or info.get("http_headers") or {}).items() if isinstance(v, str)},
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
    )


class VideoStream:
    """One ffmpeg decoding a source into JPEG frames; keeps the latest frame."""

    def __init__(self, source: Resolved, *, width: int = 640, fps: int = 15, quality: int = 7,
                 ffmpeg: Optional[str] = None, start: float = 0.0) -> None:
        self.source = source
        self.width, self.fps, self.quality, self.start_at = width, fps, quality, start
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"
        self.token = secrets.token_urlsafe(12)
        self.frame: Optional[bytes] = None
        self.seq = 0
        self.ended = False
        self.error: Optional[str] = None
        self._cond = asyncio.Condition()
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._task: Optional[asyncio.Task] = None

    def _args(self) -> list:
        a = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"]
        if self.source.headers:
            a += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in self.source.headers.items())]
        if self.start_at > 0:
            a += ["-ss", f"{self.start_at:.1f}"]
        a += ["-re", "-i", self.source.url, "-an",
              "-vf", f"scale='min({self.width},iw)':-2,fps={self.fps}",
              "-q:v", str(self.quality), "-f", "mpjpeg", "-boundary_tag", BOUNDARY, "pipe:1"]
        return a

    async def start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            *self._args(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self._task = asyncio.ensure_future(self._read())

    async def _read(self) -> None:
        out = self._proc.stdout
        try:
            while True:
                line = await out.readline()
                if not line:
                    break
                if not line.startswith(b"--"):
                    continue
                length = 0
                while True:  # part headers
                    h = await out.readline()
                    if not h or h in (b"\r\n", b"\n"):
                        break
                    k, _, v = h.decode("latin-1").partition(":")
                    if k.strip().lower() == "content-length":
                        length = int(v.strip() or 0)
                if length <= 0:
                    continue
                data = await out.readexactly(length)
                async with self._cond:
                    self.frame, self.seq = data, self.seq + 1
                    self._cond.notify_all()
        except (asyncio.IncompleteReadError, ValueError):
            pass
        finally:
            err = b""
            if self._proc and self._proc.stderr:
                try:
                    err = await asyncio.wait_for(self._proc.stderr.read(), 2)
                except Exception:
                    pass
            if err.strip():
                self.error = err.decode("utf-8", "ignore").strip()[-400:]
                _LOGGER.debug("ffmpeg: %s", self.error)
            async with self._cond:
                self.ended = True
                self._cond.notify_all()

    async def next_frame(self, after: int, timeout: float = 10.0) -> Optional[tuple]:
        """(seq, jpeg) newer than `after`, or None when the stream ended / stalled."""
        async with self._cond:
            try:
                await asyncio.wait_for(self._cond.wait_for(lambda: self.seq > after or self.ended), timeout)
            except asyncio.TimeoutError:
                return None
            if self.seq > after and self.frame is not None:
                return self.seq, self.frame
            return None

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), 3)
            except asyncio.TimeoutError:
                pass
        if self._task:
            self._task.cancel()


class MjpegServer:
    """Plain-HTTP MJPEG for the panels: GET /video/<token>.mjpeg (and .jpg)."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.host, self.port = host, port
        self.streams: Dict[str, VideoStream] = {}
        self.hls = HlsProxy()
        self._runner = None

    async def start(self) -> None:
        from aiohttp import web  # HA ships aiohttp
        app = web.Application()
        app.router.add_get("/video/{token}.mjpeg", self._mjpeg)
        app.router.add_get("/video/{token}.jpg", self._jpeg)
        self.hls.routes(app)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()
        _LOGGER.info("video: MJPEG server on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        for s in list(self.streams.values()):
            await s.stop()
        self.streams.clear()
        self.hls.sessions.clear()
        await self.hls.close()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

    def add(self, stream: VideoStream) -> None:
        self.streams[stream.token] = stream

    async def remove(self, token: str) -> None:
        s = self.streams.pop(token, None)
        if s:
            await s.stop()

    async def _jpeg(self, request):
        from aiohttp import web
        s = self.streams.get(request.match_info["token"])
        if not s or s.frame is None:
            raise web.HTTPNotFound()
        return web.Response(body=s.frame, content_type="image/jpeg", headers={"Cache-Control": "no-store"})

    async def _mjpeg(self, request):
        from aiohttp import web
        s = self.streams.get(request.match_info["token"])
        if not s:
            raise web.HTTPNotFound()
        resp = web.StreamResponse(headers={
            "Content-Type": f"multipart/x-mixed-replace; boundary={BOUNDARY}",
            "Cache-Control": "no-store", "Connection": "close",
        })
        await resp.prepare(request)
        seq = 0
        try:
            while True:
                got = await s.next_frame(seq)
                if got is None:
                    if s.ended:
                        break
                    continue
                seq, jpeg = got
                await resp.write(
                    f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n".encode() + jpeg + b"\r\n")
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        return resp


# ── Pass-through HLS (no decoding) ──────────────────────────────────────────
# The iPad 1 decodes H.264 itself (Main profile up to level 3.1, ≤ 30 fps) and
# its player speaks HLS with MPEG-TS segments, which is what YouTube serves to
# Apple clients. So the cheap path only relays bytes: we write a small master
# playlist with the variants the iPad can play, rewrite the media playlists to
# point at us, and proxy each segment from HTTPS to plain HTTP. No ffmpeg.

_AVC = re.compile(r"avc1\.(42|4d|58)([0-9a-f]{2})([0-9a-f]{2})", re.I)


def _ipad_h264(fmt: Dict[str, Any], max_height: int) -> bool:
    m = _AVC.match(fmt.get("vcodec") or "")
    return bool(m) and int(m.group(3), 16) <= 31 and (fmt.get("height") or 9999) <= max_height and (fmt.get("fps") or 30) <= 30


@dataclass
class HlsSource:
    title: Optional[str]
    video: list            # [(height, bandwidth, codecs, url)] lowest first
    audio: Optional[str]   # AAC-LC media playlist URL (None = audio muxed in video)
    headers: Dict[str, str] = field(default_factory=dict)
    duration: Optional[float] = None
    thumbnail: Optional[str] = None


def resolve_hls(url: str, max_height: int = 480) -> Optional[HlsSource]:
    """Blocking: HLS variants the iPad decodes natively, or None (then use MJPEG)."""
    if url.lower().split("?")[0].endswith(".m3u8"):
        return HlsSource(title=None, video=[(0, 0, "", url)], audio=None)
    try:
        import yt_dlp  # type: ignore
    except ImportError:
        return None
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    fmts = info.get("formats") or []
    hls = [f for f in fmts if str(f.get("protocol", "")).startswith("m3u8")]
    video = sorted(((f.get("height") or 0, int((f.get("tbr") or 0) * 1000), f.get("vcodec"), f["url"])
                    for f in hls if f.get("vcodec") not in (None, "none") and _ipad_h264(f, max_height)), key=lambda v: v[0])
    if not video:
        return None
    audio = [f for f in hls if f.get("vcodec") in (None, "none") and f.get("acodec") != "none"]
    # AAC-LC (mp4a.40.2) over HE-AAC; YouTube's HLS audio formats carry no acodec,
    # the higher itag (234) is the AAC-LC one
    audio.sort(key=lambda f: (str(f.get("acodec") or "").endswith("40.2"), f.get("format_id") or ""), reverse=True)
    return HlsSource(
        title=info.get("title"), video=video, audio=audio[0]["url"] if audio else None,
        headers={k: v for k, v in (hls[0].get("http_headers") or {}).items() if isinstance(v, str)},
        duration=info.get("duration"), thumbnail=info.get("thumbnail"),
    )


def _raw_url(url: str):
    """Signed URLs (googlevideo) break if re-encoded: pass them through as-is."""
    from yarl import URL
    return URL(url, encoded=True)


class HlsSession:
    def __init__(self, src: HlsSource) -> None:
        self.src = src
        self.token = secrets.token_urlsafe(12)
        self.segments: Dict[str, list] = {}   # playlist name -> upstream segment URLs
        self.sent_bytes = 0
        self.last_seen = 0.0

    def master(self) -> str:
        lines = ["#EXTM3U", "#EXT-X-VERSION:4"]
        if self.src.audio:
            lines.append('#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aac",NAME="Audio",DEFAULT=YES,AUTOSELECT=YES,URI="a.m3u8"')
        for i, (h, bw, codecs, _u) in enumerate(self.src.video):
            attrs = [f"BANDWIDTH={bw or 800000}"]
            if codecs:
                attrs.append(f'CODECS="{codecs},mp4a.40.2"')
            if h:
                attrs.append(f"RESOLUTION={int(h * 16 / 9) // 2 * 2}x{h}")
            if self.src.audio:
                attrs.append('AUDIO="aac"')
            lines += ["#EXT-X-STREAM-INF:" + ",".join(attrs), f"v{i}.m3u8"]
        return "\n".join(lines) + "\n"

    def upstream_playlist(self, name: str) -> Optional[str]:
        if name == "a":
            return self.src.audio
        if name.startswith("v") and name[1:].isdigit() and int(name[1:]) < len(self.src.video):
            return self.src.video[int(name[1:])][3]
        return None


class HlsProxy:
    """Mounted on the MJPEG server's app: /hls/<token>/master.m3u8 and friends."""

    def __init__(self) -> None:
        self.sessions: Dict[str, HlsSession] = {}
        self._client = None

    def routes(self, app) -> None:
        app.router.add_get("/hls/{token}/master.m3u8", self._master)
        app.router.add_get("/hls/{token}/{name}.m3u8", self._playlist)
        app.router.add_get("/hls/{token}/s/{name}/{idx}.ts", self._segment)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    def _http(self):
        import aiohttp
        if self._client is None or self._client.closed:
            self._client = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=30))
        return self._client

    def _session(self, request) -> HlsSession:
        from aiohttp import web
        s = self.sessions.get(request.match_info["token"])
        if not s:
            raise web.HTTPNotFound()
        s.last_seen = asyncio.get_running_loop().time()
        return s

    async def _master(self, request):
        from aiohttp import web
        s = self._session(request)
        return web.Response(text=s.master(), content_type="application/vnd.apple.mpegurl", headers={"Cache-Control": "no-store"})

    async def _playlist(self, request):
        from aiohttp import web
        s = self._session(request)
        name = request.match_info["name"]
        up = s.upstream_playlist(name)
        if not up:
            raise web.HTTPNotFound()
        async with self._http().get(_raw_url(up), headers=s.src.headers) as r:
            text = await r.text()
        base = up.rsplit("/", 1)[0] + "/"
        out, segs = [], []
        for line in text.splitlines():
            if line and not line.startswith("#"):
                segs.append(line if "://" in line else base + line)
                out.append(f"s/{name}/{len(segs) - 1}.ts")
            else:
                out.append(line)
        s.segments[name] = segs
        return web.Response(text="\n".join(out) + "\n", content_type="application/vnd.apple.mpegurl", headers={"Cache-Control": "no-store"})

    async def _segment(self, request):
        from aiohttp import web
        s = self._session(request)
        segs = s.segments.get(request.match_info["name"]) or []
        idx = int(request.match_info["idx"])
        if idx >= len(segs):
            raise web.HTTPNotFound()
        async with self._http().get(_raw_url(segs[idx]), headers=s.src.headers) as r:
            if r.status >= 400:
                _LOGGER.debug("hls segment %s/%s: upstream HTTP %s", request.match_info["name"], idx, r.status)
                raise web.HTTPBadGateway()
            resp = web.StreamResponse(headers={"Content-Type": "video/mp2t", "Cache-Control": "no-store"})
            if r.content_length:
                resp.content_length = r.content_length
            await resp.prepare(request)
            async for chunk in r.content.iter_chunked(64 * 1024):
                await resp.write(chunk)
                s.sent_bytes += len(chunk)
            await resp.write_eof()
            return resp


# ── Home Assistant glue ─────────────────────────────────────────────────────

SIGNAL_VIDEO_UPDATED = "ha_mqtt_dash_video_updated"
DEFAULT_PORT = 8765


class PanelVideo:
    """Per-integration owner of the video HTTP server and one video per panel.

    Default path: pass-through HLS (no decoding here; the iPad decodes H.264).
    ``transcode=True`` allows the MJPEG fallback (ffmpeg decodes) for sources
    with no stream the iPad can play; off by default, it costs real CPU.
    """

    def __init__(self, hass, bridge, port: int = DEFAULT_PORT, transcode: bool = False) -> None:
        self.hass, self.bridge, self.port, self.transcode = hass, bridge, port, transcode
        self.server: Optional[MjpegServer] = None
        self.active: Dict[str, Dict[str, Any]] = {}   # device_id -> {kind, token, title, url, state, position, …}
        self._unsub = None

    async def async_setup(self) -> None:
        from homeassistant.components import mqtt  # type: ignore
        from .const import FIXED_DEVICE_BASE
        self._unsub = await mqtt.async_subscribe(self.hass, f"{FIXED_DEVICE_BASE}/+/video", self._on_panel_event)

    async def async_unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self.server:
            await self.server.stop()
            self.server = None
        self.active.clear()

    async def _ensure_server(self) -> MjpegServer:
        if not self.server:
            self.server = MjpegServer(port=self.port)
            await self.server.start()
        return self.server

    async def _source_ip(self) -> str:
        try:
            from homeassistant.components.network import async_get_source_ip  # type: ignore
            return await async_get_source_ip(self.hass)
        except Exception:  # pragma: no cover - network integration missing
            return "127.0.0.1"

    def state(self, device_id: str) -> Dict[str, Any]:
        a = self.active.get(device_id) or {}
        stream: Optional[VideoStream] = a.get("stream")
        sess: Optional[HlsSession] = a.get("hls")
        return {
            "state": a.get("state"), "title": a.get("title"), "url": a.get("url"), "thumbnail": a.get("thumbnail"),
            "duration": a.get("duration"), "position": a.get("position"), "position_at": a.get("position_at"),
            "kind": a.get("kind"), "error": a.get("error") or (stream.error if stream else None),
            "relayed_mb": round(sess.sent_bytes / 1e6, 1) if sess else None,
            "frames": stream.seq if stream else None,
        }

    def _changed(self, device_id: str) -> None:
        from homeassistant.helpers.dispatcher import async_dispatcher_send  # type: ignore
        async_dispatcher_send(self.hass, SIGNAL_VIDEO_UPDATED, device_id)

    async def async_play(self, device_id: str, url: str, *, title: Optional[str] = None, start: float = 0.0) -> None:
        import time as _t
        await self.async_stop(device_id, tell_panel=False)
        self.active[device_id] = {"url": url, "title": title or "Loading…", "state": "loading"}
        self._changed(device_id)
        try:
            hls = await self.hass.async_add_executor_job(resolve_hls, url)
        except Exception as err:
            hls = None
            _LOGGER.debug("video: no HLS for %s: %s", url, err)
        server = await self._ensure_server()
        host = f"http://{await self._source_ip()}:{self.port}"
        if hls:
            sess = HlsSession(hls)
            server.hls.sessions[sess.token] = sess
            entry = {"kind": "hls", "token": sess.token, "hls": sess, "title": title or hls.title or url,
                     "thumbnail": hls.thumbnail, "duration": hls.duration}
            panel_url = f"{host}/hls/{sess.token}/master.m3u8"
        elif url.lower().startswith("http://"):
            entry = {"kind": "direct", "title": title or url}   # the iPad fetches it itself
            panel_url = url
        elif self.transcode:
            src = await self.hass.async_add_executor_job(resolve, url)
            stream = VideoStream(src, start=start)
            await stream.start()
            server.add(stream)
            entry = {"kind": "mjpeg", "token": stream.token, "stream": stream, "title": title or src.title or url,
                     "thumbnail": src.thumbnail, "duration": src.duration}
            panel_url = f"{host}/video/{stream.token}.mjpeg"
            start = 0.0
        else:
            self.active[device_id] = {"url": url, "title": title, "state": "error",
                                      "error": "No stream the iPad can play without transcoding"}
            self._changed(device_id)
            raise ValueError("No stream the iPad can play without transcoding (H.264 HLS up to 480p, or a plain-http file)")
        entry.update({"url": url, "state": "playing", "position": start, "position_at": _t.time()})
        self.active[device_id] = entry
        self._changed(device_id)
        payload = {"url": panel_url, "title": entry["title"]}
        if start > 0:
            payload["start"] = start
        await self.bridge.async_send_device_request(device_id, "play_video", payload)

    async def async_control(self, device_id: str, cmd: str, position: Optional[float] = None) -> None:
        extra: Dict[str, Any] = {"cmd": cmd}
        if position is not None:
            extra["position"] = float(position)
        await self.bridge.async_send_device_request(device_id, "video_control", extra)

    async def async_stop(self, device_id: str, *, tell_panel: bool = True) -> None:
        a = self.active.pop(device_id, None)
        if not a:
            return
        if self.server:
            if a.get("kind") == "mjpeg":
                await self.server.remove(a["token"])
            elif a.get("kind") == "hls":
                self.server.hls.sessions.pop(a["token"], None)
        if tell_panel:
            await self.bridge.async_send_device_request(device_id, "stop_video")
        self._changed(device_id)

    async def _on_panel_event(self, msg) -> None:
        """The panel reports {"state", "position", "duration"}: playing / paused /
        ended / error / closed."""
        import json as _json
        import time as _t
        parts = (getattr(msg, "topic", "") or "").split("/")
        if len(parts) < 4 or parts[2] not in self.active:
            return
        device_id = parts[2]
        try:
            ev = _json.loads(msg.payload if isinstance(msg.payload, str) else msg.payload.decode())
        except Exception:
            return
        state = ev.get("state") if isinstance(ev, dict) else None
        if state in ("ended", "closed", "error"):
            if state == "error":
                _LOGGER.warning("video on %s: the panel could not play the stream", device_id)
            await self.async_stop(device_id, tell_panel=False)
            return
        a = self.active[device_id]
        if state in ("playing", "paused"):
            a["state"] = state
        if isinstance(ev.get("position"), (int, float)):
            a["position"], a["position_at"] = float(ev["position"]), _t.time()
        if isinstance(ev.get("duration"), (int, float)) and ev["duration"] > 0:
            a["duration"] = float(ev["duration"])
        self._changed(device_id)


async def _demo(url: str, port: int) -> None:  # pragma: no cover - manual test helper
    loop = asyncio.get_running_loop()
    hls = await loop.run_in_executor(None, resolve_hls, url)
    if hls:
        server = MjpegServer(port=port)
        await server.start()
        sess = HlsSession(hls)
        server.hls.sessions[sess.token] = sess
        print("hls:", hls.title, [v[0] for v in hls.video], "audio" if hls.audio else "no audio")
        print(f"http://<this-host>:{port}/hls/{sess.token}/master.m3u8", flush=True)
        while True:
            await asyncio.sleep(5)
            print("sent bytes:", sess.sent_bytes, flush=True)
    src = await loop.run_in_executor(None, resolve, url)
    print("resolved:", src.title, src.url[:80])
    server = MjpegServer(port=port)
    await server.start()
    stream = VideoStream(src)
    server.add(stream)
    await stream.start()
    print(f"http://<this-host>:{port}/video/{stream.token}.mjpeg", flush=True)
    while not stream.ended:
        await asyncio.sleep(5)
        print("frames:", stream.seq, flush=True)
    print("ended", stream.error)


if __name__ == "__main__":  # pragma: no cover
    import sys
    asyncio.run(_demo(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8765))
