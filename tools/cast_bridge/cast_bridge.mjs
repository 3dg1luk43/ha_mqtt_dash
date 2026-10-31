// Cast from the YouTube app to an iPad MQTT Dashboard panel (proof of concept).
//
// Runs a YouTube "TV" receiver (yt-cast-receiver: DIAL discovery + YouTube's
// lounge protocol), so the panel appears under Cast in the YouTube app on the
// same network, like a smart TV. Every command goes to Home Assistant's
// media_player for the panel (media_player.<panel>_video); HA relays the
// H.264 stream to the iPad, which decodes it itself.
//
//   HA_URL=https://ha.example.lan HA_TOKEN=… PANEL_ENTITY=media_player.kitchen_video \
//   SCREEN_NAME="Kitchen iPad" node cast_bridge.mjs
//
// HA_TOKEN_FILE can replace HA_TOKEN. The DIAL server listens on DIAL_PORT
// (default 3000); DIAL_INTERFACES=eth0 limits it (and the SSDP replies) to the
// LAN interface, so phones aren't offered Docker bridge addresses. LAN only,
// never exposed. Pairing state is kept in STATE_FILE (default
// .cast_bridge_state.json next to this script).
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import YouTubeCastReceiver, { Player, Constants, DataStore } from 'yt-cast-receiver';

const HA_URL = (process.env.HA_URL || 'http://homeassistant.local:8123').replace(/\/$/, '');
const HA_TOKEN = process.env.HA_TOKEN || (process.env.HA_TOKEN_FILE ? readFileSync(process.env.HA_TOKEN_FILE, 'utf8').trim() : '');
const ENTITY = process.env.PANEL_ENTITY || 'media_player.dashboard_video';
const SCREEN = process.env.SCREEN_NAME || 'iPad dashboard';
const PORT = Number(process.env.DIAL_PORT || 3000);
const INTERFACES = (process.env.DIAL_INTERFACES || '').split(',').map((s) => s.trim()).filter(Boolean);
const STATE_FILE = process.env.STATE_FILE || fileURLToPath(new URL('.cast_bridge_state.json', import.meta.url));

// The library's default store (node-persist) races its own init; a JSON file does
class FileStore extends DataStore {
  constructor(path) {
    super();
    this.path = path;
    try { this.data = JSON.parse(readFileSync(path, 'utf8')); } catch { this.data = {}; }
  }
  async set(key, value) { this.data[key] = value; writeFileSync(this.path, JSON.stringify(this.data)); }
  async get(key) { return key in this.data ? this.data[key] : null; }
  async clear() { this.data = {}; writeFileSync(this.path, '{}'); }
}

if (!HA_TOKEN) {
  console.error('Set HA_TOKEN (or HA_TOKEN_FILE): a Home Assistant long-lived access token');
  process.exit(2);
}

async function ha(path, body) {
  const res = await fetch(`${HA_URL}/api/${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${HA_TOKEN}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`HA ${path}: HTTP ${res.status} ${await res.text()}`);
  return res.json();
}
const call = (service, data = {}) => ha(`services/media_player/${service}`, { entity_id: ENTITY, ...data });
const haState = () => ha(`states/${ENTITY}`);

export class PanelPlayer extends Player {
  constructor() {
    super();
    this.volume = { level: 100, muted: false };
    this.lastState = null;
  }

  async doPlay(video, position) {
    console.log(`play ${video.id} from ${position}s`);
    await call('play_media', {
      media_content_id: `https://www.youtube.com/watch?v=${video.id}`,
      media_content_type: 'video',
      extra: { start: position || 0 },
    });
    return true;
  }

  async doPause() { await call('media_pause'); return true; }
  async doResume() { await call('media_play'); return true; }
  async doStop() { await call('media_stop'); return true; }
  async doSeek(position) { await call('media_seek', { seek_position: position }); return true; }
  // The iPad's volume is the hardware buttons; remember what the sender set
  async doSetVolume(volume) { this.volume = volume; return true; }
  async doGetVolume() { return this.volume; }

  async doGetPosition() {
    try {
      const s = await haState();
      const a = s.attributes || {};
      let pos = Number(a.media_position || 0);
      if (s.state === 'playing' && a.media_position_updated_at) pos += (Date.now() - Date.parse(a.media_position_updated_at)) / 1000;
      return Math.max(0, pos);
    } catch { return 0; }
  }

  async doGetDuration() {
    try { return Number((await haState()).attributes?.media_duration || 0); } catch { return 0; }
  }

  // The panel can end or close the video itself: tell the sender
  async watch() {
    try {
      const s = (await haState()).state;
      if (this.lastState && this.lastState !== 'idle' && s === 'idle' && this.status !== Constants.PLAYER_STATUSES.STOPPED) {
        await this.notifyExternalStateChange(Constants.PLAYER_STATUSES.STOPPED);
      }
      this.lastState = s;
    } catch { /* HA restarting */ }
  }
}

// Run as a program (importing it, e.g. for a test, only gets PanelPlayer)
if (import.meta.url === new URL(`file://${process.argv[1]}`).href) await main();

async function main() {
  const player = new PanelPlayer();
  const receiver = new YouTubeCastReceiver(player, {
    device: { name: SCREEN, screenName: `YouTube on ${SCREEN}`, brand: 'Apple', model: 'iPad' },
    dial: { port: PORT, ...(INTERFACES.length ? { bindToInterfaces: INTERFACES } : {}) },
    dataStore: new FileStore(STATE_FILE),
    logLevel: process.env.LOG_LEVEL || Constants.LOG_LEVELS.INFO,
  });
  receiver.on('senderConnect', (s) => console.log(`connected: ${s.name}`));
  receiver.on('senderDisconnect', (s) => console.log(`disconnected: ${s.name}`));
  receiver.on('error', (e) => console.error('receiver error:', e?.message || e));

  await receiver.start();
  console.log(`casting target "${SCREEN}" → ${ENTITY} (DIAL on :${PORT})`);
  setInterval(() => player.watch(), 5000);
  const stop = async () => { await receiver.stop().catch(() => {}); process.exit(0); };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
}
