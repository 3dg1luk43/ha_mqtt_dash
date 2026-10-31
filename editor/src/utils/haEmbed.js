// The editor runs inside Home Assistant: the integration serves it as the
// /mqttdash-editor panel, loaded in an iframe with ?embedded=1. It borrows the
// parent HA frontend's authenticated WebSocket connection (no tokens of its own).
//
// Outside HA (`npm run dev`) the same calls return a demo panel and a few demo
// entities, so the UI can be worked on without a Home Assistant instance.
import { useEffect, useState } from 'react';
import { create } from 'zustand';
import { useEditorStore } from '../store/editorStore';
import { parseProfile, profileToState } from './profileExport';

export const EMBEDDED = (() => {
  try {
    return new URLSearchParams(window.location.search).has('embedded') &&
      window.parent !== window && !!window.parent.hassConnection;
  } catch {
    return false; // cross-origin parent
  }
})();

let connPromise = null;
function ws(msg) {
  if (!connPromise) connPromise = Promise.resolve(window.parent.hassConnection).then(({ conn }) => conn);
  return connPromise.then((conn) => conn.sendMessagePromise(msg));
}

// ── Demo data for `npm run dev` ──────────────────────────────────────────────
const DEMO_PANEL = { device_id: 'demo', has_profile: false, orientation: 'landscape', battery: 80, screen: { width: 768, height: 1024, scale: 1 } };
const DEMO_STATES = [
  ['light.kitchen', 'Kitchen lights'], ['light.living_room', 'Living room'], ['switch.coffee_machine', 'Coffee machine'],
  ['climate.house', 'Thermostat'], ['sensor.outside_temperature', 'Outside temperature', '°C'], ['person.alex', 'Alex'],
  ['media_player.kitchen', 'Kitchen speaker'], ['camera.front_door', 'Front door'], ['cover.living_room_blinds', 'Living room blinds'],
  ['weather.home', 'Home'], ['scene.dinner', 'Dinner'], ['sensor.washer_time_remaining', 'Washer time remaining', 'min'],
].map(([entity_id, name, unit]) => ({ entity_id, state: 'on', attributes: { friendly_name: name, unit_of_measurement: unit } }));

export const listDevices = () => (EMBEDDED ? ws({ type: 'ha_mqtt_dash/devices' }).then((r) => r.devices || []) : Promise.resolve([DEMO_PANEL]));
export const getProfile = (deviceId) => (EMBEDDED ? ws({ type: 'ha_mqtt_dash/get_profile', device_id: deviceId }).then((r) => r.profile) : Promise.resolve(null));
export const applyProfile = (deviceId, profile) => (EMBEDDED
  ? ws({ type: 'ha_mqtt_dash/apply_profile', device_id: deviceId, profile })
  : new Promise((res) => { console.info('[demo] deploy', deviceId, profile); setTimeout(res, 400); }));

// ── Home Assistant entities (names, units) for the pickers ──────────────────
export const useHaEntities = create((set) => ({
  entities: [],   // [{ id, name, domain, unit }]
  loaded: false,
  load: async () => {
    try {
      const states = EMBEDDED ? await ws({ type: 'get_states' }) : DEMO_STATES;
      const entities = states.map((s) => ({
        id: s.entity_id,
        name: s.attributes?.friendly_name || s.entity_id,
        domain: s.entity_id.split('.')[0],
        unit: s.attributes?.unit_of_measurement,
      })).sort((a, b) => a.name.localeCompare(b.name));
      set({ entities, loaded: true });
    } catch {
      set({ loaded: true });
    }
  },
}));

export const entityName = (id) => useHaEntities.getState().entities.find((e) => e.id === id)?.name;

/** Case-insensitive match on name and entity id; every word must match. */
export function searchEntities(entities, query, domains) {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return entities.filter((e) => {
    if (domains?.length && !domains.includes(e.domain)) return false;
    const hay = `${e.name} ${e.id}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

/** Load a profile object (as stored by the integration) into the editor. Returns false if unusable. */
export function loadProfileIntoEditor(profile, orientation, { saved = true } = {}) {
  if (!profile || typeof profile !== 'object') return false;
  const result = parseProfile(JSON.stringify(profile));
  if (!result.ok) return false;
  const s = profileToState(result.data);
  const st = useEditorStore.getState();
  // Orientation first: changing it recomputes cell sizes, the profile's grid then wins
  if (orientation === 'landscape' || orientation === 'portrait') st.setOrientation(orientation);
  st.setGridConfig(s.grid);
  st.setPages(s.pages);
  if (s.navbar_edge) st.setNavbarEdge(s.navbar_edge);
  st.setNavbarStyleAll(s.navbar_style ?? {});
  st.setNavbarShowBattery(s.navbar_show_battery !== false);
  st.setNavbarShowKeepAwake(s.navbar_show_keepawake !== false);
  if (saved) { st.clearHistory(); st.markSaved(); } // it is what the panel shows
  return true;
}

/**
 * True while HA's sidebar is hidden (narrow layout). The panel host sets
 * data-narrow on our iframe and shows its menu button in our top-left corner.
 */
export function useHostNarrow() {
  const [narrow, setNarrow] = useState(() => readNarrow());
  useEffect(() => {
    const el = hostFrame();
    if (!el) return undefined;
    const mo = new MutationObserver(() => setNarrow(readNarrow()));
    mo.observe(el, { attributes: true, attributeFilter: ['data-narrow'] });
    return () => mo.disconnect();
  }, []);
  return narrow;
}

function hostFrame() {
  try { return EMBEDDED ? window.frameElement : null; } catch { return null; }
}

function readNarrow() {
  const el = hostFrame();
  return !!el && el.dataset && el.dataset.narrow === '1';
}
