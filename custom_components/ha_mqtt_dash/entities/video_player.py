"""Per-panel "Video" media player: play a link on the panel's screen.

`media_player.play_media` with a YouTube (or other yt-dlp) link, a direct
video / HLS / RTSP URL or a media-library item; Home Assistant decodes it and
the panel shows it full screen as MJPEG (video only). Stop from HA or the
panel's close button.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components import media_source  # type: ignore
from homeassistant.components.media_player import (  # type: ignore
    MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState, MediaType,
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url  # type: ignore
from homeassistant.core import callback  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_connect  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore

from ..const import DOMAIN
from ..video_relay import SIGNAL_VIDEO_UPDATED


class PanelVideoPlayer(MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "video"
    _attr_should_poll = False
    _attr_media_content_type = MediaType.VIDEO
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.STOP | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.SEEK
    )

    def __init__(self, hass, entry, device_id: str) -> None:
        self._hass, self._entry, self._device_id = hass, entry, device_id
        self._attr_unique_id = f"{DOMAIN}:{device_id}:video"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=device_id)

    @property
    def _video(self):
        b = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        return getattr(b, "video", None)

    @property
    def _st(self) -> Dict[str, Any]:
        v = self._video
        return v.state(self._device_id) if v else {}

    async def async_added_to_hass(self) -> None:
        @callback
        def _upd(device_id: str) -> None:
            if device_id == self._device_id:
                self.async_write_ha_state()
        self.async_on_remove(async_dispatcher_connect(self._hass, SIGNAL_VIDEO_UPDATED, _upd))

    @property
    def _on(self) -> bool:
        return self._st.get("state") in ("playing", "paused", "loading")

    @property
    def state(self) -> MediaPlayerState:
        s = self._st.get("state")
        if s == "paused":
            return MediaPlayerState.PAUSED
        if s == "loading":
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.PLAYING if s == "playing" else MediaPlayerState.IDLE

    @property
    def media_title(self) -> Optional[str]:
        return self._st.get("title") if self._on else None

    @property
    def media_image_url(self) -> Optional[str]:
        return self._st.get("thumbnail") if self._on else None

    @property
    def media_position(self) -> Optional[float]:
        return self._st.get("position") if self._on else None

    @property
    def media_position_updated_at(self):
        from homeassistant.util import dt as dt_util  # type: ignore
        at = self._st.get("position_at")
        return dt_util.utc_from_timestamp(at) if at and self._on else None

    @property
    def media_duration(self) -> Optional[float]:
        return self._st.get("duration")

    @property
    def media_content_id(self) -> Optional[str]:
        return self._st.get("url")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        st = self._st
        keys = ("kind", "relayed_mb", "frames", "error")
        return {k: st.get(k) for k in keys if st.get(k) is not None}

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        title = None
        if media_source.is_media_source_id(media_id):
            play = await media_source.async_resolve_media(self._hass, media_id, self.entity_id)
            media_id = async_process_play_media_url(self._hass, play.url)
        extra = kwargs.get("extra") or {}
        start = 0.0
        if isinstance(extra, dict):
            title = extra.get("title")
            try:
                start = float(extra.get("start") or 0)
            except (TypeError, ValueError):
                start = 0.0
        await self._video.async_play(self._device_id, media_id, title=title, start=start)

    async def async_media_pause(self) -> None:
        await self._video.async_control(self._device_id, "pause")

    async def async_media_play(self) -> None:
        await self._video.async_control(self._device_id, "play")

    async def async_media_seek(self, position: float) -> None:
        await self._video.async_control(self._device_id, "seek", position)

    async def async_media_stop(self) -> None:
        await self._video.async_stop(self._device_id)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        return await media_source.async_browse_media(
            self._hass, media_content_id,
            content_filter=lambda item: item.media_content_type.startswith(("video", "image")),
        )
