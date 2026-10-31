# Video on a panel (experimental)

Play a YouTube link or a video stream on a panel from Home Assistant, or cast to it from the YouTube app on your phone.

## How it works

The iPad 1 can't reach YouTube itself: iOS 5 only speaks TLS 1.0. It can, however, decode H.264 in hardware (Main profile up to level 3.1, 30 fps), and its player understands HLS with MPEG-TS segments, which is what YouTube offers Apple devices up to 480p.

So Home Assistant decodes nothing. The integration:

1. resolves the link with yt-dlp,
2. picks the H.264 variants the iPad can play (360p and 480p) plus the AAC audio,
3. serves them to the panel from a small HTTP server on port **8765**, relaying each segment byte for byte from YouTube's HTTPS to plain HTTP.

The iPad plays it with sound in its native player. The relay costs well under 1 % of a CPU core. Plain `http://` video URLs go straight to the iPad. Sources with no stream the iPad can play are refused (an MJPEG fallback with ffmpeg exists in the code but is off: it decodes and costs real CPU).

Requirements: the panel must reach the Home Assistant host on port 8765 (plain HTTP, LAN only). The integration installs `yt-dlp`. YouTube extraction without a JavaScript runtime is deprecated in yt-dlp and may stop working in a future version.

## Playing something

Each panel has a **Video** media player (`media_player.<panel>_video`):

```yaml
action: media_player.play_media
target:
  entity_id: media_player.kitchen_video
data:
  media_content_id: https://www.youtube.com/watch?v=aqz-KE-bpKQ
  media_content_type: video
  extra:
    start: 60        # optional, seconds
```

Pause, play, seek and stop work from HA, and the panel reports its state and position back. Closing the video on the panel or reaching the end returns the entity to idle.

## The Video card

Add a **Video** card in the dashboard editor (Media group), for example on a page of its own. A video then plays inside the card at its size, with the native controls. Starting a video shows the card's page. Switching to another page (a recipe, the timers) keeps it playing, with sound. Without a Video card, videos open full screen.

## Casting from the YouTube app

`tools/cast_bridge` is a YouTube "TV" receiver ([yt-cast-receiver](https://github.com/patrickkfkan/yt-cast-receiver)): the panel shows up under **Cast** in the YouTube app on the same network, like a smart TV, and the bridge forwards play / pause / seek / stop to the panel's Video player in HA.

```bash
cd tools/cast_bridge && npm ci
HA_URL=https://homeassistant.example.lan HA_TOKEN_FILE=~/.ha_token \
PANEL_ENTITY=media_player.kitchen_video SCREEN_NAME="Kitchen iPad" DIAL_INTERFACES=eth0 \
node cast_bridge.mjs
```

Run it on any always-on machine on the LAN (Node 20+); `ha-mqtt-dash-cast.service.example` is a systemd unit for it. Discovery uses SSDP multicast, so the machine must be on the same network segment as the phones. Notes:

- The receiver re-implements YouTube's TV protocol; a change on YouTube's side can break it until the library is updated.
- `npm audit` reports moderate issues in the DIAL library's template dependencies (ejs / jake / minimatch); the high ones are overridden in `package.json`. Keep it on the LAN.
- The panel's volume is the iPad's own; the sender's volume slider has no effect.
