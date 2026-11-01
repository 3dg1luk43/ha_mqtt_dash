import asyncio
import json

from custom_components.ha_mqtt_dash import delivery as dl


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _outbox():
    clock, sent, wakes, expired = Clock(), [], [], []

    async def publish(topic, payload):
        sent.append((clock.t, topic, json.loads(payload)))

    async def wake(device_id, power):
        wakes.append((clock.t, device_id, power))
        return True

    ob = dl.PanelOutbox(publish, wake, lambda d, p: expired.append((d, p["action"])), clock=clock)
    return ob, clock, sent, wakes, expired


def _run_until(ob, clock, until, step=1.0):
    while clock.t < until:
        clock.t += step
        asyncio.run(ob.tick())


def test_unanswered_request_is_resent_then_the_panel_woken_by_mqtt_then_power():
    ob, clock, sent, wakes, expired = _outbox()
    asyncio.run(ob.send("kitchen", "mqttdash/dev/kitchen/request", {"action": "play_video", "url": "u"}, "play_video"))
    _run_until(ob, clock, 1030)
    assert [round(t - 1000) for t, _, _ in sent][:4] == [0, 4, 10, 20]
    assert [(round(t - 1000), power) for t, _, power in wakes] == [(4, False), (12, True)]
    rid = sent[0][2]["rid"]
    assert all(p["rid"] == rid for _, _, p in sent)          # the same request, the panel drops repeats
    assert ob.ack("kitchen", rid) and ob.pending("kitchen") == 0
    n = len(sent)
    _run_until(ob, clock, 1060)
    assert len(sent) == n and not expired


def test_the_panel_showing_up_gets_what_waits_at_once():
    ob, clock, sent, _, _ = _outbox()
    asyncio.run(ob.send("kitchen", "t", {"action": "notify", "message": "hi"}, "notify"))
    clock.t += 3
    asyncio.run(ob.flush("kitchen"))
    asyncio.run(ob.flush("kitchen"))                       # bursts of contact: once
    assert len(sent) == 2


def test_unacknowledged_requests_expire_and_stops_or_pauses_wake_nobody():
    ob, clock, sent, wakes, expired = _outbox()
    asyncio.run(ob.send("kitchen", "t", {"action": "stop_video"}, "stop_video"))
    asyncio.run(ob.send("kitchen", "t", {"action": "video_control", "cmd": "pause"}, "video_control"))
    _run_until(ob, clock, 1000 + dl.TTL["stop_video"] + 2)
    assert not wakes and ob.pending("kitchen") == 0
    assert sorted(a for _, a in expired) == ["stop_video", "video_control"]


def test_power_wakes_are_rate_limited_per_panel():
    ob, clock, sent, wakes, _ = _outbox()
    asyncio.run(ob.send("kitchen", "t", {"action": "notify", "message": "a"}, "notify"))
    _run_until(ob, clock, 1020)
    asyncio.run(ob.send("kitchen", "t", {"action": "notify", "message": "b"}, "notify"))
    _run_until(ob, clock, 1040)
    assert sum(1 for _, _, power in wakes if power) == 1
