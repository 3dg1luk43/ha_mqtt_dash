// Device-frame geometry shared by the canvas and drag/drop math.

// Navigation bar dimensions in logical points — must match the real MQTTDash app.
export const NAV_H = 44;   // horizontal bar (top / bottom)
export const NAV_W = 80;   // vertical sidebar (left / right)

/**
 * How much the widget content area is offset from the screen's top-left corner.
 * bottom/right nav: widgets start at (0,0); nav bar is at the opposite edge.
 */
export function getNavOffset(navbar_edge) {
  if (navbar_edge === 'top')  return { x: 0, y: NAV_H };
  if (navbar_edge === 'left') return { x: NAV_W, y: 0 };
  return { x: 0, y: 0 }; // bottom or right — widgets start at (0,0)
}

export function getFrameDims(device, orientation) {
  // Use logical points — the coordinate system MQTTDash uses for layout.
  // All iPads are 768×1024 pt; bezel is a fixed pt value (approx real physical size).
  const [pw, ph] = device.points ?? [768, 1024];
  const [screenW, screenH] = orientation === 'landscape' ? [ph, pw] : [pw, ph];
  const bezelSide = orientation === 'landscape' ? 50 : 32;
  const bezelTop  = orientation === 'landscape' ? 32 : 50;
  const bezelBot  = orientation === 'landscape' ? 32 : 50;
  const frameW = screenW + 2 * bezelSide;
  const frameH = screenH + bezelTop + bezelBot;
  return { screenW, screenH, frameW, frameH, bezelLeft: bezelSide, bezelTop };
}

/** Scale at which the device frame fits the canvas area (16 px padding each side, never above 1). */
export function fitScale(device, orientation, containerW, containerH) {
  const { frameW, frameH } = getFrameDims(device, orientation);
  return Math.max(0.05, Math.min(1, (containerH - 32) / frameH, (containerW - 32) / frameW));
}
