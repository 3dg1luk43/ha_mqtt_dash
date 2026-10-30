export default function SensorConfig({ widget, onChange }) {
  return (
    <div>
      <h3 style={sectionTitle}>Sensor</h3>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Unit</label>
        <input
          type="text"
          value={widget.unit ?? ''}
          onChange={(e) => onChange({ unit: e.target.value })}
          placeholder="e.g. °C, %, W"
          style={inputStyle}
        />
      </div>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>
          Preview value <span style={{ color: 'var(--ed-text-3)', fontWeight: 400 }}>(editor simulation only)</span>
        </label>
        <input
          type="text"
          value={widget.preview_value ?? ''}
          onChange={(e) => onChange({ preview_value: e.target.value || undefined })}
          placeholder="e.g. 42"
          style={inputStyle}
        />
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
