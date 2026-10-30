// Common fields for every widget: label, entity_id, x, y, w, h, protected
import EntityAutocomplete from './EntityAutocomplete';

export default function CommonFields({ widget, onChange }) {
  function handleChange(field, value) {
    onChange({ [field]: value });
  }

  function num(val, min = 0) {
    const v = parseInt(val, 10);
    return isNaN(v) ? min : Math.max(min, v);
  }

  return (
    <div>
      <h3 style={sectionTitle}>Common</h3>

      <Field label="ID">
        <input
          type="text"
          value={widget.id ?? ''}
          onChange={(e) => handleChange('id', e.target.value)}
          style={inputStyle}
        />
      </Field>
      <Field label="Label">
        <input
          type="text"
          value={widget.label ?? ''}
          onChange={(e) => handleChange('label', e.target.value)}
          style={inputStyle}
          placeholder="Display name"
        />
      </Field>
      {widget.type !== 'label' && widget.type !== 'clock' && widget.type !== 'sousvide' && widget.type !== 'appliance' && (
        <Field label="Entity ID">
          <EntityAutocomplete
            value={widget.entity_id ?? ''}
            onChange={(v) => handleChange('entity_id', v)}
            placeholder="e.g. light.bedroom"
          />
        </Field>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 8 }}>
        {[['x', 'Col X', 0], ['y', 'Row Y', 0], ['w', 'Width (cells)', 1], ['h', 'Height (cells)', 1]].map(([f, lbl, mn]) => (
          <div key={f}>
            <label style={{ fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 }}>{lbl}</label>
            <input
              type="number"
              min={mn}
              value={widget[f] ?? mn}
              onChange={(e) => handleChange(f, num(e.target.value, mn))}
              style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' }}
            />
          </div>
        ))}
      </div>

      {(widget.type === 'light' || widget.type === 'switch' || widget.type === 'button' || widget.type === 'scene' || widget.type === 'cover') && (
        <Field label="Protected">
          <input
            type="checkbox"
            checked={!!widget.protected}
            onChange={(e) => handleChange('protected', e.target.checked)}
            style={{ width: 16, height: 16 }}
          />
        </Field>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, gap: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--ed-text-2)', flexShrink: 0, minWidth: 70 }}>{label}</label>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 10px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
