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

Every panel shows up under **Cast** in the YouTube app on phones on the same network, like a smart TV ("Kitchen iPad" for the panel `kitchen`). Casting plays the video on the panel through its Video player; play, pause, seek, stop, next / previous in the phone's queue work, and pausing, closing or finishing the video on the panel shows on the phone. At the end of a video the next one in the queue plays.

Home Assistant does this itself (a port of the receiver side of [yt-cast-receiver](https://github.com/patrickkfkan/yt-cast-receiver)): it answers the phones' SSDP searches on UDP 1900 (alongside HA's own SSDP discovery), serves the DIAL description on the video server's port 8765, and keeps each panel linked to YouTube's "lounge" service, which relays the phone's commands. Turn it off in the integration options (**YouTube casting**).

- Phones and the HA host must be on the same network segment (multicast), and HA must run with host networking.
- Pairing survives restarts: the panel stays in the app's list of linked TVs.
- A phone that just drops (app closed, Wi-Fi lost) leaves the video playing; **Disconnect** in the app stops it.
- YouTube Music casting and "up next" autoplay aren't offered.
- It re-implements YouTube's TV protocol; a change on YouTube's side can break it.
- The panel's volume is the iPad's own; the sender's volume slider has no effect.

`tools/cast_bridge` is the earlier standalone version (Node, run on another LAN machine against HA's API). Don't run it for a panel that HA already offers, or the panel is listed twice.
