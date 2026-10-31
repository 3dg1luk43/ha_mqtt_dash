import asyncio
import json
import socket
import time

from custom_components.ha_mqtt_dash import cast_receiver as cr
from custom_components.ha_mqtt_dash import video_relay as vr


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── lounge messages ──

INIT_BODY = (
    '898\n[[0,["c","135730815279298","",8]]\n,[1,["S","GS-abc"]]\n'
    ',[2,["loungeStatus",{"devices":"[{\\"name\\":\\"Küche 📺\\",\\"id\\":\\"screen\\",\\"type\\":\\"LOUNGE_SCREEN\\"}]"}]]\n]\n'
    '16\n[[3,["noop"]]\n]\n'
).encode()


def test_chunks_split_anywhere_parse_into_messages():
    reader = cr.ChunkReader()
    got = []
    for i in range(len(INIT_BODY)):          # byte by byte, splitting UTF-8 sequences too
        got += reader.feed(INIT_BODY[i:i + 1])
    assert [(m.aid, m.name) for m in got] == [(0, "c"), (1, "S"), (2, "loungeStatus"), (3, "noop")]
    assert got[0].payload == ["135730815279298", "", 8]     # several args: a list
    assert got[1].payload == "GS-abc"                        # one arg: the value
    assert json.loads(got[2].payload["devices"])[0]["name"] == "Küche 📺"
    assert got[3].payload is None
    assert cr.parse_messages(INIT_BODY) == got


def test_malformed_chunk_is_skipped():
    msgs = cr.parse_messages(b'5\n[[1,"x\n16\n[[5,["noop"]]\n]\n<html>error</html>\n')
    assert [(m.aid, m.name) for m in msgs] == [(5, "noop")]


def test_bind_params_query_strings():
    p = cr.BindParams("dev-1", "YouTube on Kitchen iPad")
    try:
        p.query("init")
        raise AssertionError("query without a lounge token")
    except cr.LoungeError:
        pass
    p.lounge_token = "TOKEN"
    rid = p.rid
    q = p.query("init")
    assert q["device"] == "LOUNGE_SCREEN" and q["id"] == "dev-1" and q["theme"] == "cl" and q["RID"] == rid
    assert json.loads(q["deviceInfo"])["clientName"] == "TVHTML5" and json.loads(q["deviceInfo"])["model"] == "iPad"
    assert p.rid == rid + 1 and len(q["zx"]) == 12
    for m in cr.parse_messages(INIT_BODY):
        p.update(m)
    assert (p.sid, p.gsessionid, p.aid) == ("135730815279298", "GS-abc", 3)
    q = p.query("send")                          # own message: current AID, then +1
    assert (q["SID"], q["gsessionid"], q["AID"], q["RID"]) == ("135730815279298", "GS-abc", 3, rid + 1) and p.aid == 4
    q = p.query("send", 9)                       # a reply: the sender's AID, no increment
    assert q["AID"] == 9 and p.aid == 9
    q = p.query("rpc")
    assert (q["RID"], q["TYPE"], q["CI"], q["AID"]) == ("rpc", "xmlhttp", 0, 9) and "deviceInfo" not in q
    url = str(cr.bind_url(q))
    assert url.startswith(cr.URL_BIND + "?") and "name=YouTube%20on%20Kitchen%20iPad" in url


# ── SSDP ──

TARGET = cr.SsdpTarget("1234-uuid", "http://192.168.0.247:8765/dial/kitchen/ssdp/device-desc.xml")


def _msearch(st):
    return (f'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 1\r\nST: {st}\r\n\r\n').encode()


def test_dial_msearch_gets_a_unicast_reply():
    (reply,) = cr.msearch_replies(_msearch(cr.DIAL_ST), [TARGET])
    start, headers = cr.parse_ssdp(reply)
    assert reply.startswith(b"HTTP/1.1 200 OK\r\n") and reply.endswith(b"\r\n\r\n")
    assert headers["LOCATION"] == TARGET.location and headers["ST"] == cr.DIAL_ST
    assert headers["USN"] == f"uuid:1234-uuid::{cr.DIAL_ST}" and headers["CACHE-CONTROL"] == "max-age=1800"
    assert "EXT" in headers and headers["DATE"].endswith("GMT")
    assert cr.parse_ssdp(cr.msearch_replies(_msearch("uuid:1234-uuid"), [TARGET])[0])[1]["USN"] == "uuid:1234-uuid"
    two = [TARGET, cr.SsdpTarget("5678", "http://h/dial/office/ssdp/device-desc.xml")]
    assert len(cr.msearch_replies(_msearch(cr.DIAL_DEVICE), two)) == 2


def test_other_searches_and_notifies_get_no_reply():
    for st in ("ssdp:all", "upnp:rootdevice", "urn:schemas-upnp-org:device:MediaRenderer:1", "uuid:other"):
        assert cr.msearch_replies(_msearch(st), [TARGET]) == []
    assert cr.msearch_replies(cr.notify(TARGET)[0], [TARGET]) == []


def test_notify_alive_and_byebye():
    alive = [cr.parse_ssdp(m) for m in cr.notify(TARGET)]
    assert {h["NT"] for _, h in alive} == {cr.DIAL_ST, cr.DIAL_DEVICE}
    assert all(m == "NOTIFY" and h["NTS"] == "ssdp:alive" and h["LOCATION"] == TARGET.location for m, h in alive)
    bye = [cr.parse_ssdp(m)[1] for m in cr.notify(TARGET, alive=False)]
    assert all(h["NTS"] == "ssdp:byebye" and "LOCATION" not in h for h in bye)


# ── the receiver against a fake PanelVideo ──

class FakeVideo:
    def __init__(self):
        self.calls, self.st, self.last_end = [], {}, {}

    async def async_play(self, device_id, url, *, title=None, start=0.0):
        self.calls.append(("play", device_id, url, start))
        self.last_end.pop(device_id, None)
        self.st = {"state": "playing", "url": url, "position": start, "position_at": time.time(), "duration": 200.0}

    async def async_control(self, device_id, cmd, position=None):
        self.calls.append((cmd, device_id, position))

    async def async_stop(self, device_id, *, tell_panel=True):
        self.calls.append(("stop", device_id))
        self.st = {}

    def state(self, device_id):
        return dict(self.st) or {"state": None}

    def panel_reports(self, how):   # what video_relay does when the panel ends / closes the video
        self.last_end["kitchen"] = how
        self.st = {}


def _receiver():
    video = FakeVideo()
    r = cr.YouTubeReceiver("Kitchen iPad", cr.PanelPlayer(video, "kitchen"), base_url="http://192.168.0.247:8765/dial/kitchen")
    sent = []

    async def send(msgs):
        sent.extend(msgs)
        return True
    r.lounge.send = send
    return r, video, sent


PHONE = {"id": "phone-1", "name": "Pixel", "type": "REMOTE_CONTROL", "theme": "cl", "capabilities": "que,mus"}


def _lounge_status(device_id, ui="true", devices=(PHONE,)):
    return cr.Message(7, "loungeStatus", {"devices": json.dumps(list(devices)),
                                          "connectionEventDetails": json.dumps({"deviceId": device_id, "ui": ui})})


def _names(sent):
    return [m.name for m in sent]


def _states(sent):
    return [m.payload["state"] for m in sent if m.name == "onStateChange"]


async def _connected():
    r, video, sent = _receiver()
    await r.handle(cr.Message(2, "loungeStatus", {"devices": "[]"}), initial=True)
    assert sent == [] and r.senders == {}
    await r.handle(_lounge_status("phone-1"))
    assert list(r.senders) == ["phone-1"]
    assert _names(sent) == ["onAutoplayModeChanged", "onHasPreviousNextChanged", "nowPlaying", "onStateChange"]
    assert sent[0].payload == {"autoplayMode": "UNSUPPORTED"} and sent[2].payload == {} and _states(sent) == [cr.IDLE]
    sent.clear()
    await r.handle(cr.Message(8, "setPlaylist", {"listId": "RQ1", "videoId": "aaa", "currentIndex": "0",
                                                 "currentTime": "12.5", "videoIds": "aaa,bbb", "ctt": "CTT"}))
    return r, video, sent


def test_cast_commands_drive_the_panel_video():
    async def run():
        r, video, sent = await _connected()
        assert video.calls == [("play", "kitchen", "https://www.youtube.com/watch?v=aaa", 12.5)]
        assert _states(sent) == [cr.LOADING, cr.PLAYING]
        now = [m.payload for m in sent if m.name == "nowPlaying"][-1]
        assert (now["videoId"], now["listId"], now["currentIndex"], now["ctt"], now["duration"]) == ("aaa", "RQ1", 0, "CTT", 200.0)
        assert 12.5 <= now["currentTime"] < 14
        assert [m.payload for m in sent if m.name == "onHasPreviousNextChanged"][-1] == {"hasPrevious": False, "hasNext": True}

        for msg, call, state in (
            (cr.Message(9, "pause"), ("pause", "kitchen", None), cr.PAUSED),
            (cr.Message(10, "play"), ("play", "kitchen", None), cr.PLAYING),
            (cr.Message(11, "stopVideo"), ("stop", "kitchen"), cr.STOPPED),
        ):
            sent.clear()
            await r.handle(msg)
            assert video.calls[-1] == call and _states(sent) == [state]

        await r.handle(cr.Message(12, "play"))          # stopped: plays the current video again
        assert video.calls[-1] == ("play", "kitchen", "https://www.youtube.com/watch?v=aaa", 0.0)
        sent.clear()
        await r.handle(cr.Message(13, "seekTo", {"newTime": "30"}))
        assert video.calls[-1] == ("seek", "kitchen", 30.0) and _states(sent) == [cr.LOADING, cr.PLAYING]
        assert [m.payload["currentTime"] for m in sent if m.name == "onStateChange"][0] == 30.0

        await r.handle(cr.Message(14, "next"))
        assert video.calls[-1][2:] == ("https://www.youtube.com/watch?v=bbb", 0.0)
        await r.handle(cr.Message(15, "next"))           # end of the queue: stop
        assert video.calls[-1] == ("stop", "kitchen") and r.status == cr.STOPPED
        await r.handle(cr.Message(16, "previous"))
        assert video.calls[-1][2] == "https://www.youtube.com/watch?v=aaa"

        sent.clear()
        await r.handle(cr.Message(17, "setVolume", {"volume": "40", "muted": "false"}))
        await r.handle(cr.Message(18, "getVolume"))
        assert [m.payload for m in sent] == [{"volume": 40, "muted": False}] * 2

        sent.clear()                                      # queue edited on the phone: no new playback
        n = len(video.calls)
        await r.handle(cr.Message(19, "updatePlaylist", {"listId": "RQ1", "videoIds": "zzz,aaa,bbb"}))
        assert len(video.calls) == n and r.current["index"] == 1 and _names(sent) == ["nowPlaying", "onHasPreviousNextChanged"]
        await r.handle(cr.Message(20, "updatePlaylist", {"listId": "RQ1", "videoIds": "zzz"}))   # current removed
        assert video.calls[-1] == ("stop", "kitchen")

    asyncio.run(run())


def test_panel_side_changes_reach_the_phone():
    async def run():
        r, video, sent = await _connected()
        sent.clear()
        video.st["state"] = "paused"                      # paused on the panel itself
        await r.handle(cr.Message(None, "_panel"))
        assert _states(sent) == [cr.PAUSED] and r.status == cr.PAUSED
        video.st["state"] = "playing"
        await r.handle(cr.Message(None, "_panel"))
        assert r.status == cr.PLAYING

        video.panel_reports("ended")                      # ended: next in the queue
        await r.handle(cr.Message(None, "_panel"))
        assert video.calls[-1][2] == "https://www.youtube.com/watch?v=bbb" and r.status == cr.PLAYING

        sent.clear()
        video.panel_reports("closed")                     # closed on the panel: stopped, no new video
        n = len(video.calls)
        await r.handle(cr.Message(None, "_panel"))
        assert len(video.calls) == n and r.status == cr.STOPPED and _states(sent) == [cr.STOPPED]

        await r.handle(cr.Message(21, "setPlaylist", {"listId": "RQ1", "videoId": "bbb", "currentIndex": "1",
                                                      "videoIds": "aaa,bbb"}))   # cast the same one again
        assert video.calls[-1][2] == "https://www.youtube.com/watch?v=bbb"
        video.st["url"] = "https://www.youtube.com/watch?v=other"   # something else played from HA
        await r.handle(cr.Message(None, "_panel"))
        assert r.status == cr.STOPPED

    asyncio.run(run())


def test_dropped_phone_keeps_playing_disconnect_stops():
    async def run():
        r, video, sent = await _connected()
        await r.handle(_lounge_status("phone-1", ui="false", devices=()))   # app killed / lost Wi-Fi
        assert r.senders == {} and video.calls[-1][0] == "play"
        await r.handle(_lounge_status("phone-1"))                          # back
        await r.handle(_lounge_status("phone-1", ui="true", devices=()))   # "Disconnect" in the app
        assert video.calls[-1] == ("stop", "kitchen") and r.current is None and r.status == cr.IDLE

    asyncio.run(run())


# ── DIAL over the video server ──

class FakeLounge:
    def __init__(self):
        self.ready, self.screen_id, self.codes = True, "screen", []

    async def register_pairing_code(self, code):
        self.codes.append(code)


def test_dial_endpoints_on_the_video_server():
    import aiohttp

    async def run():
        port = _free_port()
        server = vr.MjpegServer(host="127.0.0.1", port=port)
        await server.start()
        base = f"http://127.0.0.1:{port}/dial/kitchen"
        r = cr.YouTubeReceiver("Kitchen iPad", None, base_url=base, uuid_="1234-uuid")
        r.lounge = FakeLounge()
        cast = cr.PanelCast(None, None)
        cast.receivers["kitchen"] = r
        server.mounts["dial"] = cast._dial                # mounted after start
        async with aiohttp.ClientSession() as http:
            async with http.get(f"{base}/ssdp/device-desc.xml") as resp:
                body = await resp.text()
                assert resp.status == 200 and resp.headers["Application-URL"] == f"{base}/apps"
                assert "<friendlyName>Kitchen iPad</friendlyName>" in body and "<UDN>uuid:1234-uuid</UDN>" in body
                assert f"<deviceType>{cr.DIAL_DEVICE}</deviceType>" in body
            async with http.get(f"{base}/apps/YouTube") as resp:
                body = await resp.text()
                assert resp.status == 200 and "<state>running</state>" in body and 'allowStop="false"' in body
            launch = "pairingCode=abc-123&theme=cl&v=dQw4w9WgXcQ&t=0"
            for origin, status in ((None, 200), ("package:com.google.ios.youtube", 200), ("https://www.youtube.com", 200),
                                   ("http://evil.lan", 403), ("https://youtube.com.evil.lan", 403)):
                headers = {"Content-Type": "text/plain; charset=\"utf-8\""} | ({"Origin": origin} if origin else {})
                async with http.post(f"{base}/apps/YouTube", data=launch, headers=headers) as resp:
                    assert resp.status == status, origin
                    if status == 200:
                        assert resp.headers["Location"] == f"{base}/apps/YouTube/run"
            assert r.lounge.codes == ["abc-123"] * 3
            async with http.delete(f"{base}/apps/YouTube/run") as resp:
                assert resp.status == 405
            async with http.get(f"{base}/apps") as resp:
                assert resp.status == 204
            for url in (f"http://127.0.0.1:{port}/dial/office/apps/YouTube", f"{base}/apps/Netflix",
                        f"http://127.0.0.1:{port}/video/nope.mjpeg", f"http://127.0.0.1:{port}/other/x"):
                async with http.get(url) as resp:
                    assert resp.status == 404, url
            r.lounge.ready = False                        # not linked to YouTube (yet)
            async with http.get(f"{base}/apps/YouTube") as resp:
                assert "<state>stopped</state>" in await resp.text()
            async with http.post(f"{base}/apps/YouTube", data=launch) as resp:
                assert resp.status == 503
        await server.stop()

    asyncio.run(run())


def test_names_and_urls():
    assert cr.friendly_name("living_room") == "Living room iPad"
    assert cr.video_id_of(cr.watch_url("dQw4w9WgXcQ")) == "dQw4w9WgXcQ"
    assert cr.video_id_of("https://example.com/watch?v=x") is None and cr.video_id_of(None) is None


def test_receivers_follow_the_option_and_the_panels(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    class FakeSsdp:
        def __init__(self, targets, iface):
            self.targets, self.iface, self.running = targets, iface, False

        async def start(self):
            self.running = True

        async def stop(self):
            self.running = False

        def announce(self, targets, alive=True):
            pass

    async def noop(*_a, **_k):
        return None
    monkeypatch.setattr(cr, "SsdpResponder", FakeSsdp)
    monkeypatch.setattr(cr.YouTubeReceiver, "start", lambda self: None)
    monkeypatch.setattr(cr.YouTubeReceiver, "stop", noop)
    server = vr.MjpegServer()

    async def ensure_server():
        return server

    async def source_ip():
        return "192.168.0.247"
    stored = {"kitchen": {"uuid": "u-1", "screen_id": "s-1", "device_id": "d-1"}}
    bridge = SimpleNamespace(
        entry=SimpleNamespace(options={}),
        cfg={"devices": [{"device_id": "kitchen"}, {"device_id": "bad id/x"}, {"device_id": "office"}]},
        video=SimpleNamespace(port=8765, server=server, _ensure_server=ensure_server, _source_ip=source_ip),
        _storage_helper=SimpleNamespace(get_cast=lambda did: dict(stored.get(did, {}))),
    )

    async def run():
        cast = cr.PanelCast(MagicMock(), bridge)
        await cast.async_sync()                           # on by default
        assert sorted(cast.receivers) == ["kitchen", "office"]
        k = cast.receivers["kitchen"]
        assert (k.uuid, k.lounge.screen_id, k.params.id) == ("u-1", "s-1", "d-1")   # pairing survives restarts
        assert k.location == "http://192.168.0.247:8765/dial/kitchen/ssdp/device-desc.xml" and k.name == "Kitchen iPad"
        assert server.mounts["dial"] == cast._dial and cast.ssdp.running and cast.ssdp.iface == "192.168.0.247"
        assert {t.uuid for t in cast._targets()} == {"u-1", cast.receivers["office"].uuid}
        bridge.cfg["devices"] = [{"device_id": "kitchen"}]
        await cast.async_sync()
        assert list(cast.receivers) == ["kitchen"] and cast.receivers["kitchen"] is k
        bridge.entry.options = {"yt_cast": False}
        await cast.async_sync()
        assert cast.receivers == {} and "dial" not in server.mounts and cast.ssdp is None

    asyncio.run(run())
