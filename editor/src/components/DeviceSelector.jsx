import { useEditorStore } from '../store/editorStore';
import { DEVICE_MODELS } from '../data/deviceModels';

export default function DeviceSelector({ compact = false }) {
  const { device, setDevice, orientation, setOrientation } = useEditorStore();

  function handleModelChange(e) {
    const model = DEVICE_MODELS.find((m) => m.key === e.target.value);
    if (model) setDevice({ ...model });
  }

  function handleCustomPixels(axis, value) {
    const v = parseInt(value, 10);
    if (isNaN(v) || v < 1) return;
    const updated = { ...device };
    updated.pixels = axis === 'w'
      ? [v, device.pixels[1]]
      : [device.pixels[0], v];
    updated.scale = null; // unknown for custom
    setDevice(updated);
  }

  const [screenW, screenH] = orientation === 'landscape'
    ? [device.pixels[1], device.pixels[0]]
    : device.pixels;

  const ORIENTATIONS = [['portrait', '▯'], ['landscape', '▭']];

  if (compact) {
    // Toolbar variant (inside HA): model picker + orientation toggle, details in the tooltip
    const info = device.key === 'custom' ? `${screenW}×${screenH}px (${orientation})` : `${screenW}×${screenH}px · ${device.note}`;
    return (
      <>
        <select className="ed-select" value={device.key} onChange={handleModelChange} title={`Device model — ${info}`} style={{ flex: '0 1 auto', maxWidth: 170 }}>
          {DEVICE_MODELS.map((m) => (
            <option key={m.key} value={m.key}>{m.name}</option>
          ))}
        </select>
        {device.key === 'custom' && (
          <>
            <input type="number" className="ed-select" value={device.pixels[0]} onChange={(e) => handleCustomPixels('w', e.target.value)} title="Width px" style={{ width: 70, flexShrink: 0, cursor: 'text' }} />
            <input type="number" className="ed-select" value={device.pixels[1]} onChange={(e) => handleCustomPixels('h', e.target.value)} title="Height px" style={{ width: 70, flexShrink: 0, cursor: 'text' }} />
          </>
        )}
        <span className="ed-seg" role="group" aria-label="Orientation">
          {ORIENTATIONS.map(([o, icon]) => (
            <button key={o} aria-pressed={orientation === o} onClick={() => setOrientation(o)} title={o.charAt(0).toUpperCase() + o.slice(1)}>
              {icon}
            </button>
          ))}
        </span>
      </>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 12px', background: 'var(--ed-surface-2)', borderBottom: '1px solid var(--ed-divider)', flexWrap: 'nowrap', whiteSpace: 'nowrap', overflow: 'hidden', flexShrink: 0 }}>
      <label style={{ fontSize: 12, color: 'var(--ed-text-2)', fontWeight: 500 }}>Device:</label>
      <select
        value={device.key}
        onChange={handleModelChange}
        style={{ fontSize: 12, padding: '3px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-surface)', color: 'var(--ed-text)' }}
      >
        {DEVICE_MODELS.map((m) => (
          <option key={m.key} value={m.key}>{m.name}</option>
        ))}
      </select>

      {/* Orientation toggle */}
      <div style={{ display: 'flex', gap: 2 }}>
        {ORIENTATIONS.map(([o, icon]) => (
          <button
            key={o}
            onClick={() => setOrientation(o)}
            title={o.charAt(0).toUpperCase() + o.slice(1)}
            style={{
              padding: '3px 8px',
              fontSize: 13,
              border: '1px solid var(--ed-border)',
              borderRadius: 4,
              background: orientation === o ? 'var(--ed-primary)' : 'var(--ed-surface)',
              color: orientation === o ? 'var(--ed-on-primary)' : 'var(--ed-text-2)',
              cursor: 'pointer',
            }}
          >
            {icon}
          </button>
        ))}
      </div>

      {device.key === 'custom' ? (
        <>
          <input
            type="number"
            value={device.pixels[0]}
            onChange={(e) => handleCustomPixels('w', e.target.value)}
            style={{ width: 64, fontSize: 12, padding: '2px 4px', border: '1px solid var(--ed-border)', borderRadius: 4 }}
            placeholder="Width px"
          />
          <span style={{ fontSize: 12, color: 'var(--ed-text-2)' }}>×</span>
          <input
            type="number"
            value={device.pixels[1]}
            onChange={(e) => handleCustomPixels('h', e.target.value)}
            style={{ width: 64, fontSize: 12, padding: '2px 4px', border: '1px solid var(--ed-border)', borderRadius: 4 }}
            placeholder="Height px"
          />
          <span style={{ fontSize: 11, color: 'var(--ed-text-3)' }}>px — {screenW}×{screenH} ({orientation})</span>
        </>
      ) : (
        <span style={{ fontSize: 11, color: 'var(--ed-text-3)' }}>
          {screenW}×{screenH}px · {device.note}
        </span>
      )}
    </div>
  );
}
