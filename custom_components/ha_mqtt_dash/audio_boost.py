"""Make quiet videos louder: re-encode only their audio rendition.

The video stays pass-through (see video_relay). YouTube reports each video's
loudness (YT-EXT-ABSOLUTE-LOUDNESS in its HLS master); a video quieter than
QUIET_BELOW gets its audio raised towards TARGET with a limiter, so the iPad 1's
small speakers are loud enough.

YouTube's HLS audio is "packed audio": an ID3 tag with the segment's
timestamp, then ADTS AAC-LC frames. One ffmpeg per video re-encodes the frames
continuously (no clicks at segment joins), a few segments ahead of the player;
each boosted segment gets exactly as many frames as the original plus the
original's ID3 tag, so the playlist stays YouTube's own (same timeline,
seeking, durations). A jump (seek) restarts ffmpeg there after one warm-up
segment. A pause stops ffmpeg until playback resumes. Anything unexpected
falls back to the original audio.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Awaitable, Callable, Dict, Optional

_LOGGER = logging.getLogger(__name__)

QUIET_BELOW = -17.0   # LUFS; louder videos pass through untouched
TARGET = -13.0        # LUFS to raise quiet ones to
MAX_GAIN = 15.0       # dB
AHEAD = 3             # segments prepared ahead of the newest request
IDLE_STOP = 60        # s without a request (paused): stop ffmpeg, restart on the next one
MAX_CRASHES = 3       # ffmpeg exits mid-track this often: serve the original audio


def gain_for(loudness: Optional[float]) -> float:
    """dB to add, 0 = leave the audio alone."""
    if loudness is None or loudness >= QUIET_BELOW:
        return 0.0
    return round(min(MAX_GAIN, TARGET - loudness), 1)


# ── packed audio (ID3 + ADTS) ────────────────────────────────────────────────

def adts_frames(buf: bytes) -> tuple:
    """(complete ADTS frames, leftover bytes)."""
    frames, i, n = [], 0, len(buf)
    while i + 7 <= n:
        if buf[i] != 0xFF or (buf[i + 1] & 0xF6) != 0xF0:
            i += 1
            continue
        size = (buf[i + 3] & 3) << 11 | buf[i + 4] << 3 | buf[i + 5] >> 5
        if size < 7:
            i += 1
            continue
        if i + size > n:
            break
        frames.append(buf[i:i + size])
        i += size
    return frames, buf[i:]


def split_packed(seg: bytes) -> Optional[tuple]:
    """(ID3 header, AAC-LC frames) of a packed-audio segment, None for anything else."""
    head = b""
    if seg[:3] == b"ID3" and len(seg) >= 10:
        size = (seg[6] & 0x7F) << 21 | (seg[7] & 0x7F) << 14 | (seg[8] & 0x7F) << 7 | (seg[9] & 0x7F)
        end = 10 + size + (10 if seg[5] & 0x10 else 0)
        head, seg = seg[:end], seg[end:]
    frames, _rest = adts_frames(seg)
    if not frames or frames[0][2] >> 6 != 1:     # ADTS profile 1 = AAC-LC (HE-AAC frames don't map 1:1)
        return None
    return head, frames


async def _reap(proc) -> None:
    """Collect a dead ffmpeg's broken stdin pipe (else asyncio logs "exception never retrieved")."""
    try:
        await asyncio.wait_for(proc.stdin.wait_closed(), 1)
    except Exception:
        pass


# ── the booster ──────────────────────────────────────────────────────────────

class AudioBooster:
    """Boosted copies of one audio rendition's segments, made on demand."""

    def __init__(self, fetch: Callable[[int], Awaitable[bytes]], count: int, gain_db: float, ffmpeg: Optional[str] = None) -> None:
        self.fetch, self.count, self.gain = fetch, count, gain_db
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"
        self.done: Dict[int, bytes] = {}
        self.heads: Dict[int, bytes] = {}       # segment -> its original ID3 tag
        self.counts: Dict[int, int] = {}        # segment -> number of AAC frames
        self.wanted = 0
        self.start = 0           # first segment the running worker produces
        self.next_feed = 0       # next upstream segment the worker feeds in
        self.failed = False
        self.finished = False    # the worker reached the end of the track
        self.idle = False        # the worker was stopped for lack of requests
        self.ended = False       # the running worker produces nothing more
        self.crashes = 0
        self.boosted = 0         # segments served boosted (diagnostics)
        self._cond = asyncio.Condition()
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._tasks: list = []

    def _args(self) -> list:
        return [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "aac", "-i", "pipe:0",
                "-af", f"volume={self.gain}dB,alimiter=limit=0.97:level=false",
                "-c:a", "aac", "-b:a", "128k", "-flush_packets", "1", "-f", "adts", "pipe:1"]

    async def get(self, idx: int) -> Optional[bytes]:
        """Boosted segment idx, or None (caller serves the original)."""
        if self.failed or not 0 <= idx < self.count:
            return None
        async with self._cond:
            running = self._proc is not None and self._proc.returncode is None
            if idx not in self.done and (not running or not self.start <= idx <= self.next_feed + AHEAD):
                await self._restart(idx)       # first request, or a seek out of the window
            else:
                self.wanted = max(self.wanted, idx)
            self._cond.notify_all()
            try:
                # A worker that finished without it (e.g. a tiny last segment merged into
                # the one before): serve the original
                await asyncio.wait_for(self._cond.wait_for(lambda: idx in self.done or self.failed or self.finished or self.ended), 30)
            except asyncio.TimeoutError:
                _LOGGER.debug("audio boost: segment %s timed out", idx)
                return None
            data = self.done.get(idx)
        if data:
            self.boosted += 1
        return data

    async def _restart(self, k: int) -> None:
        await self._stop_worker()
        warm = max(0, k - 1)
        self.start, self.next_feed, self.wanted = k, warm, k
        self.finished = self.idle = self.ended = False
        self.done = {i: d for i, d in self.done.items() if i >= k}
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._args(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        except OSError as err:
            _LOGGER.warning("audio boost off: can't run ffmpeg (%s)", err)
            self.failed = True
            return
        self._tasks = [asyncio.ensure_future(self._feed(self._proc)), asyncio.ensure_future(self._read(self._proc, warm))]

    def _emit(self, idx: int, data: bytes) -> None:
        if idx >= self.start:
            self.done[idx] = data
            for old in [i for i in self.done if i < self.wanted - 4]:
                del self.done[old]
            asyncio.ensure_future(self._notify())

    async def _notify(self) -> None:
        async with self._cond:
            self._cond.notify_all()

    async def _feed(self, proc) -> None:
        try:
            while self.next_feed < self.count:
                async with self._cond:
                    try:
                        await asyncio.wait_for(self._cond.wait_for(lambda: self.next_feed <= self.wanted + AHEAD), IDLE_STOP)
                    except asyncio.TimeoutError:
                        self.idle = True
                        proc.kill()
                        return
                i = self.next_feed
                packed = split_packed(await self.fetch(i))
                if packed is None:
                    _LOGGER.debug("audio boost off: segment %s isn't packed AAC-LC audio", i)
                    self.failed = True
                    await self._notify()
                    return
                self.heads[i], frames = packed
                self.counts[i] = len(frames)
                proc.stdin.write(b"".join(frames))
                await proc.stdin.drain()
                self.next_feed = i + 1
            proc.stdin.close()
        except (BrokenPipeError, ConnectionResetError, asyncio.CancelledError):
            pass
        except Exception as err:
            _LOGGER.debug("audio boost: feeding failed: %s", err)
            self.failed = True
            await self._notify()

    async def _read(self, proc, first: int) -> None:
        """Deal the boosted frames out to segments, frame count by frame count."""
        seg, frames, rest, skip = first, [], b"", 1    # the encoder's first frame is priming
        try:
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                got, rest = adts_frames(rest + chunk)
                for f in got:
                    if skip:
                        skip -= 1
                        continue
                    frames.append(f)
                    if len(frames) >= self.counts.get(seg, 1 << 30):
                        self._emit(seg, self.heads.get(seg, b"") + b"".join(frames))
                        seg, frames = seg + 1, []
            self.finished = self.next_feed >= self.count
            if frames and self.finished:   # the track's last segment (a short one)
                self._emit(seg, self.heads.get(seg, b"") + b"".join(frames))
            await proc.wait()
            await _reap(proc)
        except asyncio.CancelledError:
            return
        if not self.finished and not self.idle:
            self.crashes += 1
            _LOGGER.debug("audio boost: ffmpeg exited mid-track (%s)", proc.returncode)
            if self.crashes >= MAX_CRASHES:
                _LOGGER.warning("audio boost off for this video: ffmpeg keeps failing")
                self.failed = True
        self.ended = True
        await self._notify()

    async def _stop_worker(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks = []
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
                await asyncio.wait_for(self._proc.wait(), 3)
            except (ProcessLookupError, asyncio.TimeoutError):
                pass
        if self._proc:
            await _reap(self._proc)
        self._proc = None

    async def close(self) -> None:
        await self._stop_worker()
        self.done.clear()
