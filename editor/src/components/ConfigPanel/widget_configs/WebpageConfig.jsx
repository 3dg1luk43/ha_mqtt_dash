export default function WebpageConfig({ widget, onChange }) {
  return (
    <div>
      <h3 style={sectionTitle}>Webpage</h3>
      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 }}>
        Embeds a web page inside the tile. SSL certificate errors are silently bypassed —
        local HTTPS servers without a valid cert work fine.
      </p>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>URL</label>
        <input
          type="text"
          value={widget.stream_url ?? ''}
          onChange={(e) => onChange({ stream_url: e.target.value })}
          placeholder="http://192.168.1.100/page"
          style={inputStyle}
        />
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
