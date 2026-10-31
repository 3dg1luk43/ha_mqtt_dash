// The canvas is the panel's screen in UIKit points (every supported iPad is
// 768×1024 pt; Retina only doubles the pixels). Built from the screen info the
// app sends in its hello, so the frame always matches the selected panel.

export const DEFAULT_DEVICE = { key: 'ipad', name: 'iPad', points: [768, 1024], pixels: [768, 1024], scale: 1, retina: false };

export function deviceForScreen(screen) {
  const w = Number(screen?.width), h = Number(screen?.height);
  if (!(w > 0 && h > 0)) return DEFAULT_DEVICE;
  const scale = Number(screen.scale) > 0 ? Number(screen.scale) : 1;
  const points = [Math.min(w, h), Math.max(w, h)];
  return {
    key: `screen-${points[0]}x${points[1]}@${scale}`,
    name: scale > 1 ? 'iPad (Retina)' : 'iPad',
    points,
    pixels: points.map((p) => Math.round(p * scale)),
    scale,
    retina: scale > 1,
  };
}
