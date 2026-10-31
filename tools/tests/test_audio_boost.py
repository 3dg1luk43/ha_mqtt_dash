import asyncio
import re
import shutil
import subprocess

import pytest

from custom_components.ha_mqtt_dash import audio_boost as ab

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def test_only_quiet_videos_are_boosted():
    assert ab.gain_for(None) == 0 and ab.gain_for(-13.0) == 0 and ab.gain_for(-16.9) == 0
    assert ab.gain_for(-20.0) == 7.0
    assert ab.gain_for(-40.0) == ab.MAX_GAIN


def _id3_timestamp(pts: int) -> bytes:
    """The ID3 tag HLS packed audio starts with (as YouTube sends it)."""
    data = b"com.apple.streaming.transportStreamTimestamp\x00" + pts.to_bytes(8, "big")
    frame = b"PRIV" + len(data).to_bytes(4, "big") + b"\x00\x00" + data
    n = len(frame)
    return b"ID3\x03\x00\x00" + bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F]) + frame


def _packed_segments(seconds: int, gain_db: float, per_seg: int = 200):
    adts = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                           "-af", f"volume={gain_db}dB", "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "128k",
                           "-f", "adts", "pipe:1"], check=True, capture_output=True).stdout
    frames, _ = ab.adts_frames(adts)
    return [_id3_timestamp(126000 + i * per_seg * 1024 * 90000 // 44100) + b"".join(frames[i:i + per_seg])
            for i in range(0, len(frames), per_seg)]


def _mean_db(segs) -> float:
    raw = b"".join(b"".join(ab.split_packed(s)[1]) for s in segs)
    out = subprocess.run(["ffmpeg", "-hide_banner", "-f", "aac", "-i", "pipe:0", "-af", "volumedetect", "-f", "null", "-"],
                         input=raw, capture_output=True).stderr.decode()
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", out).group(1))


def test_packed_audio_is_recognised():
    seg = _id3_timestamp(1234) + b"\xff\xf1\x50\x80" + bytes([0x00, 0xFF, 0xFC])   # ADTS LC header, 7 bytes, no payload
    head, frames = ab.split_packed(seg)
    assert head.startswith(b"ID3") and len(frames) == 1
    assert ab.split_packed(b"\x47" + bytes(187)) is None                        # MPEG-TS: not handled, original served


@needs_ffmpeg
def test_booster_keeps_tags_and_frame_counts_and_raises_the_level():
    originals = _packed_segments(30, -30.0)

    async def fetch(i):
        return originals[i]

    async def run():
        b = ab.AudioBooster(fetch, len(originals), 10.0)
        out = [await b.get(i) for i in (0, 1, 2)]
        await b.close()
        return out

    out = asyncio.run(run())
    for i, seg in enumerate(out):
        head, frames = ab.split_packed(seg)
        o_head, o_frames = ab.split_packed(originals[i])
        assert head == o_head and len(frames) == len(o_frames)
    gain = _mean_db(out) - _mean_db(originals[:3])
    assert 8.5 < gain < 11.5


@needs_ffmpeg
def test_booster_restarts_on_a_seek_out_of_its_window():
    originals = _packed_segments(60, -30.0)
    fed = []

    async def fetch(i):
        fed.append(i)
        return originals[i]

    async def run():
        b = ab.AudioBooster(fetch, len(originals), 6.0)
        await b.get(0)
        seg = await b.get(9)                  # far ahead: restart at 9 after one warm-up segment
        await b.close()
        return seg

    seg = asyncio.run(run())
    assert ab.split_packed(seg)[0] == ab.split_packed(originals[9])[0]
    assert 8 in fed and 5 not in fed[fed.index(8):]
