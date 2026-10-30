export default function ClockConfig({ widget, onChange }) {
  return (
    <div>
      <h3 style={sectionTitle}>Clock</h3>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Time pattern</label>
        <input
          type="text"
          value={widget.time_pattern ?? ''}
          onChange={(e) => onChange({ time_pattern: e.target.value })}
          placeholder="e.g. HH:MM:SS"
          style={inputStyle}
        />
        <p style={{ fontSize: 10, color: 'var(--ed-text-3)', margin: '4px 0 0' }}>
          Tokens: HH (24h hour), hh (12h), MM (min), SS (sec), DD (day), Mo (month), YY (year)
        </p>
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
