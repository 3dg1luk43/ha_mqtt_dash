// CSS-rendered iPad frame (home-button era).
// screenW/screenH are in logical points (same for all iPads: 768×1024).

export default function DeviceFrame({ screenW, screenH, orientation = 'portrait', children }) {
  const isLandscape = orientation === 'landscape';

  // Fixed bezel in logical points — matches getFrameDims
  const bezelSide = isLandscape ? 50 : 32;
  const bezelTop  = isLandscape ? 32 : 50;
  const bezelBot  = isLandscape ? 32 : 50;
  const radius    = 28;
  const homeSize  = 36;
  const homeOffset = 8;
  const camSize   = 8;
  const camOffset = 18;

  const frameW = screenW + 2 * bezelSide;
  const frameH = screenH + bezelTop + bezelBot;

  const homeBtn = isLandscape
    ? { right: homeOffset, top: '50%', transform: 'translateY(-50%)', position: 'absolute' }
    : { bottom: homeOffset, left: '50%', transform: 'translateX(-50%)', position: 'absolute' };

  const camera = isLandscape
    ? { left: camOffset, top: '50%', transform: 'translateY(-50%)', position: 'absolute' }
    : { top: camOffset, left: '50%', transform: 'translateX(-50%)', position: 'absolute' };

  return (
    <div style={{ width: frameW, height: frameH, position: 'relative', flexShrink: 0 }}>
      {/* Outer frame */}
      <div style={{
        position: 'absolute',
        inset: 0,
        borderRadius: radius,
        background: '#2a2a2a',
        boxShadow: '0 8px 40px #0006, 0 0 0 2px #555 inset',
      }} />

      {/* Camera */}
      <div style={{
        ...camera,
        width: camSize,
        height: camSize,
        borderRadius: '50%',
        background: '#444',
        border: `1px solid #666`,
      }} />

      {/* Home button */}
      <div style={{
        ...homeBtn,
        width: homeSize,
        height: homeSize,
        borderRadius: '50%',
        background: '#1a1a1a',
        border: `2px solid #555`,
        boxShadow: '0 0 0 2px #333 inset',
      }} />

      {/* Screen */}
      <div style={{
        position: 'absolute',
        top: bezelTop,
        left: bezelSide,
        width: screenW,
        height: screenH,
        background: '#1a1a2e',
        overflow: 'hidden',
      }}>
        {children}
      </div>
    </div>
  );
}
