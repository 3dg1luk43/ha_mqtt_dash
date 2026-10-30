// Embedded mode: mirror Home Assistant's active theme onto the editor's --ed-*
// tokens. The iframe is same-origin with HA, so the parent's computed CSS
// variables are readable directly. Re-applied when HA switches theme / dark
// mode (MutationObserver on the parent <html>), plus a cheap 5 s re-check.
import { EMBEDDED } from './haEmbed';

// [editor token, HA variables in order of preference, fallback]
const MAP = [
  ['--ed-bg', ['--primary-background-color']],
  ['--ed-surface', ['--ha-card-background', '--card-background-color']],
  ['--ed-surface-2', ['--secondary-background-color']],
  ['--ed-input-bg', ['--input-fill-color', '--mdc-text-field-fill-color', '--secondary-background-color']],
  ['--ed-text', ['--primary-text-color']],
  ['--ed-text-2', ['--secondary-text-color']],
  ['--ed-text-3', ['--disabled-text-color']],
  ['--ed-primary', ['--primary-color']],
  ['--ed-on-primary', ['--text-primary-color'], '#ffffff'],
  ['--ed-divider', ['--divider-color'], 'rgba(127, 127, 127, 0.2)'],
  ['--ed-radius', ['--ha-card-border-radius'], '12px'],
  ['--ed-success', ['--success-color']],
  ['--ed-error', ['--error-color']],
  ['--ed-warning', ['--warning-color']],
];

let lastSig = '';

function readTheme() {
  const doc = window.parent.document;
  const cs = getComputedStyle(doc.documentElement);
  const get = (name) => cs.getPropertyValue(name).trim();
  const out = {};
  for (const [token, names, fallback] of MAP) {
    const v = names.map(get).find(Boolean) || fallback;
    if (v) out[token] = v;
  }
  const font = get('--ha-font-family-body') || get('--paper-font-body1_-_font-family') ||
    (doc.body ? getComputedStyle(doc.body).fontFamily : '');
  if (font) out['--ed-font'] = font;
  return out;
}

/** Relative luminance (0..1) of an rgb()/hex color string, or null if unparseable. */
function luminance(color) {
  let r, g, b;
  const m = color.match(/rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i);
  if (m) [r, g, b] = m.slice(1, 4).map(Number);
  else {
    const h = color.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)?.[1];
    if (!h) return null;
    const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
    [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
  }
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function apply() {
  let theme;
  try { theme = readTheme(); } catch { return; }
  const sig = JSON.stringify(theme);
  if (sig === lastSig) return;
  lastSig = sig;
  const root = document.documentElement;
  for (const [token] of MAP) root.style.removeProperty(token);
  root.style.removeProperty('--ed-font');
  for (const [k, v] of Object.entries(theme)) root.style.setProperty(k, v);
  const lum = theme['--ed-bg'] ? luminance(theme['--ed-bg']) : null;
  // Native controls (select popups, scrollbars, checkboxes) follow dark mode too
  root.style.colorScheme = lum != null && lum < 0.35 ? 'dark' : 'light';
  root.dataset.edTheme = 'ha';
}

/** Start following HA's theme. No-op outside HA. Call once, before first render. */
export function followHaTheme() {
  if (!EMBEDDED) return;
  apply();
  try {
    const target = window.parent.document.documentElement;
    new MutationObserver(apply).observe(target, { attributes: true, attributeFilter: ['style', 'class'] });
  } catch { /* parent not observable — the interval below still catches changes */ }
  setInterval(apply, 5000);
}
