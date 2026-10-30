export default function LabelConfig({ widget, onChange }) {
  return (
    <div>
      <h3 style={sectionTitle}>Label</h3>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Text content</label>
        <textarea
          value={widget.text ?? ''}
          onChange={(e) => onChange({ text: e.target.value })}
          placeholder="Static text to display"
          rows={3}
          style={{ ...inputStyle, resize: 'vertical' }}
        />
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
