// Responsive breakpoints, from the editor's own viewport (inside HA that is the
// iframe, i.e. HA's content area, not the browser window).
import { useSyncExternalStore } from 'react';

function subscribe(cb) {
  window.addEventListener('resize', cb);
  return () => window.removeEventListener('resize', cb);
}
const getWidth = () => window.innerWidth;

export function useLayout() {
  const vw = useSyncExternalStore(subscribe, getWidth);
  return {
    vw,
    // Add panel: icon rail (opens the full pane over the canvas) when narrow
    paletteVariant: vw < 1180 ? 'rail' : 'panel',
    // Settings: slide-over drawer when narrow so the canvas keeps the space
    configMode: vw < 1080 ? 'drawer' : 'side',
    tight: vw < 960,
  };
}
