import asyncio
import shutil
import socket
import subprocess
import urllib.request

import pytest

from custom_components.ha_mqtt_dash import video_relay as vr

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def test_direct_media_urls_skip_the_resolver():
    for url in ("http://nas/movie.mp4", "https://cdn/x/index.m3u8?token=1", "rtsp://cam/stream"):
        assert vr.resolve(url).url == url


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@needs_ffmpeg
def test_stream_serves_jpeg_frames_over_mjpeg(tmp_path):
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-t", "3",
                    "-pix_fmt", "yuv420p", str(clip)], check=True)
    port = _free_port()

    async def run():
        server = vr.MjpegServer(host="127.0.0.1", port=port)
        await server.start()
        stream = vr.VideoStream(vr.Resolved(url=str(clip)), width=160, fps=5)
        server.add(stream)
        await stream.start()
        got = await stream.next_frame(0, timeout=10)
        assert got and got[1][:2] == b"\xff\xd8" and got[1][-2:] == b"\xff\xd9"
        loop = asyncio.get_running_loop()
        head = await loop.run_in_executor(None, lambda: urllib.request.urlopen(
            f"http://127.0.0.1:{port}/video/{stream.token}.mjpeg", timeout=5).read(200))
        assert head.startswith(f"--{vr.BOUNDARY}\r\nContent-Type: image/jpeg".encode())
        assert await loop.run_in_executor(None, lambda: urllib.request.urlopen(
            f"http://127.0.0.1:{port}/video/{stream.token}.jpg", timeout=5).read(2)) == b"\xff\xd8"
        await server.stop()

    asyncio.run(run())


def test_only_h264_the_ipad_decodes_is_offered():
    ok = {"vcodec": "avc1.4D401F", "height": 480, "fps": 30}
    assert vr._ipad_h264(ok, 480)
    assert not vr._ipad_h264({**ok, "vcodec": "avc1.4D4020", "height": 720, "fps": 60}, 720)  # level 3.2, 60 fps
    assert not vr._ipad_h264({**ok, "vcodec": "avc1.64001F"}, 480)                            # High profile
    assert not vr._ipad_h264({**ok, "vcodec": "vp09.00.30.08"}, 480)
    assert not vr._ipad_h264({**ok, "height": 720}, 480)
    assert vr._ipad_h264({"vcodec": "avc1.4D401F", "height": 720, "fps": 25}, 720)                # 720p25 Main L3.1


def test_hls_proxy_rewrites_playlists_and_relays_segments_untouched():
    from aiohttp import web

    seg = b"\x47" + bytes(range(256)) * 40          # stand-in TS bytes
    seen = []

    async def playlist(request):
        return web.Response(text="#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:4.0,\nseg%3D1.ts\n#EXT-X-ENDLIST\n")

    async def segment(request):
        seen.append(request.raw_path)
        return web.Response(body=seg, content_type="video/mp2t")

    async def run():
        up_port, port = _free_port(), _free_port()
        up = web.Application()
        up.router.add_get("/v.m3u8", playlist)
        up.router.add_get("/{name}", segment)
        runner = web.AppRunner(up)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", up_port).start()
        server = vr.MjpegServer(host="127.0.0.1", port=port)
        await server.start()
        sess = vr.HlsSession(vr.HlsSource(title="t", video=[(480, 1291038, "avc1.4D401F", f"http://127.0.0.1:{up_port}/v.m3u8")],
                                          audio=f"http://127.0.0.1:{up_port}/v.m3u8"))
        server.hls.sessions[sess.token] = sess
        base = f"http://127.0.0.1:{port}/hls/{sess.token}"
        loop = asyncio.get_running_loop()
        get = lambda path: loop.run_in_executor(None, lambda: urllib.request.urlopen(base + path, timeout=5).read())
        master = (await get("/master.m3u8")).decode()
        assert 'TYPE=AUDIO' in master and "RESOLUTION=852x480" in master and "v0.m3u8" in master
        media = (await get("/v0.m3u8")).decode()
        assert "s/v0/0.ts" in media and "#EXT-X-ENDLIST" in media
        assert await get("/s/v0/0.ts") == seg
        assert seen == ["/seg%3D1.ts"]             # signed path passed through as-is
        await server.stop()
        await runner.cleanup()

    asyncio.run(run())


def test_original_soundtrack_beats_auto_dubs():
    tracks = [
        {"format_id": "234-1", "language": "de-DE", "format_note": "Deutsch - dubbed-auto"},
        {"format_id": "234-9", "language": "uk", "format_note": "Українська - dubbed-auto"},
        {"format_id": "233-10", "language": "en-US", "language_preference": 10, "format_note": "American English - original (original)"},
        {"format_id": "234-10", "language": "en-US", "language_preference": 10, "format_note": "American English - original (original)"},
    ]
    best = sorted(tracks, key=lambda f: vr._audio_rank(f, "en-US"), reverse=True)[0]
    assert best["format_id"] == "234-10"          # original, and the AAC-LC variant of it
    plain = [{"format_id": "233"}, {"format_id": "234"}]   # single-language video
    assert sorted(plain, key=lambda f: vr._audio_rank(f, None), reverse=True)[0]["format_id"] == "234"


def test_a_direct_master_playlist_offers_its_h264_variants():
    master = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="en",DEFAULT=YES,URI="audio/en.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,CODECS="avc1.4d401e,mp4a.40.2",AUDIO="aud"
360/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=6000000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2",AUDIO="aud"
1080/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=640x360,CODECS="hvc1.1.6.L93.B0",AUDIO="aud"
/hevc/360.m3u8
"""
    src = vr.parse_master("https://cdn.example/live/master.m3u8", master)
    assert src.video == [(360, 800000, "avc1.4d401e", "https://cdn.example/live/360/index.m3u8")]
    assert src.audio == "https://cdn.example/live/audio/en.m3u8"
    assert vr.parse_master("https://cdn.example/a.m3u8", "#EXTM3U\n#EXTINF:4,\nseg.ts\n") is None


def test_a_stop_while_resolving_wins():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    resolving = asyncio.Event()

    async def run():
        release = asyncio.Event()

        async def executor(fn, *args):
            resolving.set()
            await release.wait()
            return vr.HlsSource(title="t", video=[(480, 1, "avc1.4D401F", "https://x/v.m3u8")], audio=None)

        hass = SimpleNamespace(async_add_executor_job=executor)
        bridge = SimpleNamespace(cfg={}, async_send_device_request=AsyncMock())
        pv = vr.PanelVideo(hass, bridge, port=_free_port())
        pv._yt_dlp_ready = True
        pv._changed = lambda d: None
        pv._source_ip = AsyncMock(return_value="127.0.0.1")
        play = asyncio.ensure_future(pv.async_play("kitchen", "https://youtu.be/x"))
        await resolving.wait()
        await pv.async_stop("kitchen")
        release.set()
        await play
        assert "kitchen" not in pv.active
        assert not (pv.server and pv.server.hls.sessions)
        assert [c.args[1] for c in bridge.async_send_device_request.call_args_list] == ["stop_video"]
        if pv.server:
            await pv.server.stop()

    asyncio.run(run())


def test_a_failed_play_does_not_stay_loading():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    async def run():
        async def executor(fn, *args):
            return None
        bridge = SimpleNamespace(cfg={}, async_send_device_request=AsyncMock())
        pv = vr.PanelVideo(SimpleNamespace(async_add_executor_job=executor), bridge, port=_free_port())
        pv._yt_dlp_ready = True
        pv._changed = lambda d: None
        pv._source_ip = AsyncMock(return_value="127.0.0.1")
        with pytest.raises(ValueError):
            await pv.async_play("kitchen", "https://example.com/page")
        assert pv.state("kitchen")["state"] == "error"
        if pv.server:
            await pv.server.stop()

    asyncio.run(run())


def test_an_old_yt_dlp_is_reported_not_silently_empty():
    from types import SimpleNamespace
    old, new = SimpleNamespace(version=SimpleNamespace(__version__="2026.07.04")), SimpleNamespace(version=SimpleNamespace(__version__="2026.10.26"))
    with pytest.raises(vr.YtDlpTooOld, match="restart Home Assistant"):
        vr._check_yt_dlp(old)
    vr._check_yt_dlp(new)
    assert vr.needs_yt_dlp("https://youtu.be/x") and not vr.needs_yt_dlp("https://cdn/x/master.m3u8?t=1")
