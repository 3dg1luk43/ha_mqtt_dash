// Responsive layout breakpoints, driven by the editor's own viewport (inside HA
// that is the iframe, i.e. HA's content area — not the browser window).
import { useSyncExternalStore } from 'react';
import { EMBEDDED } from './haEmbed';

function subscribe(cb) {
  window.addEventListener('resize', cb);
  return () => window.removeEventListener('resize', cb);
}
const getWidth = () => window.innerWidth;

export function useLayout() {
  const vw = useSyncExternalStore(subscribe, getWidth);
  return {
    vw,
    // Widget palette: icon rail when narrow; compact 2-col grid inside HA
    paletteVariant: vw < 1200 ? 'rail' : EMBEDDED ? 'grid' : 'list',
    // Config panel: slide-over drawer when narrow so the canvas keeps the space
    configMode: vw < 1100 ? 'drawer' : 'side',
    // Toolbar: secondary actions move into a "⋯" menu
    toolbarMenu: vw < 1280,
    tight: vw < 960,
  };
}
