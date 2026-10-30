import EntityAutocomplete from '../EntityAutocomplete';

export default function CameraConfig({ widget, onChange }) {
  const overlay = widget.overlay_button ?? {};

  function setOverlay(field, value) {
    onChange({ overlay_button: { ...overlay, [field]: value } });
  }

  // camera_source is editor-only (not exported); derive it for imported profiles.
  const source = widget.camera_source
    ?? (widget.camera_entity ? 'entity' : widget.stream_url ? 'url' : 'entity');

  // Uncontrolled so partial input like "0." isn't clobbered; only valid values are committed.
  function setRefresh(val) {
    if (val.trim() === '') return onChange({ refresh_interval: undefined });
    const v = parseFloat(val);
    if (Number.isFinite(v) && v > 0) onChange({ refresh_interval: v });
  }

  return (
    <div>
      <h3 style={sectionTitle}>Camera</h3>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Source</label>
        <div style={{ display: 'flex', gap: 10 }}>
          {[['entity', 'HA camera entity'], ['url', 'Direct URL']].map(([v, lbl]) => (
            <label key={v} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
              <input
                type="radio"
                name="camera_source"
                value={v}
                checked={source === v}
                onChange={() => onChange({ camera_source: v })}
              />
              {lbl}
            </label>
          ))}
        </div>
      </div>

      {source === 'entity' ? (
        <div style={{ marginBottom: 8 }}>
          <label style={labelStyle}>Camera entity <span style={hint}>(camera.*)</span></label>
          <EntityAutocomplete
            value={widget.camera_entity ?? ''}
            onChange={(v) => onChange({ camera_entity: v })}
            placeholder="camera.front_door"
          />
          <p style={hintP}>
            HA fetches frames and relays them to the iPad — use this for WebRTC / go2rtc /
            RTSP cameras the iPad can&apos;t play directly.
          </p>
        </div>
      ) : (
        <div style={{ marginBottom: 8 }}>
          <label style={labelStyle}>Stream URL</label>
          <input
            type="text"
            value={widget.stream_url ?? ''}
            onChange={(e) => onChange({ stream_url: e.target.value })}
            placeholder="http://192.168.1.50/mjpeg"
            style={inputStyle}
          />
          <p style={hintP}>
            Must be a plain-HTTP MJPEG stream or JPEG snapshot URL (no HTTPS, RTSP, HLS or WebRTC).
          </p>
        </div>
      )}

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Refresh interval (seconds) <span style={hint}>(blank = 1)</span></label>
        <input
          type="number"
          min={0.1}
          step={0.5}
          key={widget.id}
          defaultValue={widget.refresh_interval ?? ''}
          onChange={(e) => setRefresh(e.target.value)}
          placeholder="1"
          style={{ ...inputStyle, width: 80 }}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={labelStyle}>Scale mode</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {['fit', 'stretch'].map((m) => (
            <label key={m} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
              <input
                type="radio"
                name="scale_mode"
                value={m}
                checked={(widget.scale_mode ?? 'fit') === m}
                onChange={() => onChange({ scale_mode: m })}
              />
              {m}
            </label>
          ))}
        </div>
      </div>

      <h4 style={{ fontSize: 12, fontWeight: 600, color: 'var(--ed-text)', margin: '0 0 6px' }}>Overlay Button (optional)</h4>
      <div style={{ marginBottom: 6 }}>
        <label style={labelStyle}>Button label</label>
        <input type="text" value={overlay.label ?? ''} onChange={(e) => setOverlay('label', e.target.value)} placeholder="e.g. Light" style={inputStyle} />
      </div>
      <div style={{ marginBottom: 6 }}>
        <label style={labelStyle}>Entity ID</label>
        <EntityAutocomplete
          value={overlay.entity_id ?? ''}
          onChange={(v) => setOverlay('entity_id', v)}
          placeholder="light.camera_light"
        />
      </div>
      <div style={{ marginBottom: 6 }}>
        <label style={labelStyle}>Action</label>
        <select value={overlay.action ?? 'toggle'} onChange={(e) => setOverlay('action', e.target.value)} style={inputStyle}>
          <option value="toggle">toggle</option>
          <option value="turn_on">turn_on</option>
          <option value="turn_off">turn_off</option>
        </select>
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const hint = { color: 'var(--ed-text-3)', fontWeight: 400 };
const hintP = { fontSize: 10, color: 'var(--ed-text-3)', margin: '3px 0 0', lineHeight: 1.4 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
