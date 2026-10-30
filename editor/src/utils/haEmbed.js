// Embedded mode: the editor running inside Home Assistant (integration panel
// at /mqttdash-editor, loaded in an iframe with ?embedded=1). It borrows the
// parent HA frontend's authenticated WebSocket connection, so there is no
// OAuth, no token handling and no API-access window.
import { useEffect, useState } from 'react';
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
function haConnection() {
  if (!connPromise) {
    connPromise = Promise.resolve(window.parent.hassConnection).then(({ conn }) => conn);
  }
  return connPromise;
}

async function ws(msg) {
  const conn = await haConnection();
  return conn.sendMessagePromise(msg);
}

export const listDevices = () => ws({ type: 'ha_mqtt_dash/devices' }).then((r) => r.devices || []);
export const getProfile = (deviceId) => ws({ type: 'ha_mqtt_dash/get_profile', device_id: deviceId }).then((r) => r.profile);
export const applyProfile = (deviceId, profile) => ws({ type: 'ha_mqtt_dash/apply_profile', device_id: deviceId, profile });
export const listEntityIds = () => ws({ type: 'get_states' }).then((states) => states.map((s) => s.entity_id).sort());

/** Load a profile object (as stored by the integration) into the editor. Returns false if unusable. */
export function loadProfileIntoEditor(profile, orientation) {
  if (!profile || typeof profile !== 'object') return false;
  const result = parseProfile(JSON.stringify(profile));
  if (!result.ok) return false;
  const s = profileToState(result.data);
  const st = useEditorStore.getState();
  // Orientation first: changing it recomputes cell sizes, the profile's grid then wins
  if (orientation === 'landscape' || orientation === 'portrait') st.setOrientation(orientation);
  st.setGridConfig(s.grid);
  st.setPages(s.pages);
  st.setBanner(s.banner ?? '');
  if (s.navbar_edge) st.setNavbarEdge(s.navbar_edge);
  st.setNavbarShowBattery(s.navbar_show_battery !== false);
  st.setNavbarShowKeepAwake(s.navbar_show_keepawake !== false);
  if (s.device_settings) st.setDeviceSettings(s.device_settings);
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
