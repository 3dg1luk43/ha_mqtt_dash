export default function MealieConfig({ widget, onChange }) {
  const section = widget.visible_section ?? 'ingredients';

  return (
    <div>
      <h3 style={sectionTitle}>Mealie</h3>
      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 }}>
        Connects to a self-hosted{' '}
        <strong>Mealie</strong> instance. Without a recipe slug it shows a
        scrollable picker; with one it jumps straight to that recipe.
      </p>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Instance URL</label>
        <input
          type="text"
          value={widget.mealie_url ?? ''}
          onChange={(e) => onChange({ mealie_url: e.target.value })}
          placeholder="http://192.168.1.100:9000"
          style={inputStyle}
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>API key (Bearer token)</label>
        <input
          type="password"
          value={widget.mealie_api_key ?? ''}
          onChange={(e) => onChange({ mealie_api_key: e.target.value })}
          placeholder="eyJ..."
          style={inputStyle}
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Recipe slug <span style={{ color: 'var(--ed-text-3)', fontWeight: 400 }}>(optional — omit for picker)</span></label>
        <input
          type="text"
          value={widget.recipe_slug ?? ''}
          onChange={(e) => onChange({ recipe_slug: e.target.value || undefined })}
          placeholder="pasta-carbonara"
          style={inputStyle}
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Show</label>
        <div style={{ display: 'flex', gap: 4 }}>
          {[['ingredients', 'Ingredients'], ['steps', 'Steps'], ['both', 'Both']].map(([v, lbl]) => (
            <button
              key={v}
              onClick={() => onChange({ visible_section: v })}
              style={{
                flex: 1, fontSize: 11, padding: '4px 0',
                border: '1px solid var(--ed-border)', borderRadius: 4,
                background: section === v ? 'var(--ed-primary)' : 'var(--ed-surface-2)',
                color: section === v ? 'var(--ed-on-primary)' : 'var(--ed-text-2)',
                cursor: 'pointer',
              }}
            >
              {lbl}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
