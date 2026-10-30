import EntityAutocomplete from '../EntityAutocomplete';

export default function SousvideConfig({ widget, onChange }) {
  return (
    <div>
      <h3 style={sectionTitle}>Sous Vide</h3>
      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 }}>
        <code>entity_id</code> drives active state — value <strong>cooking</strong> activates the tile;
        anything else (idle / off / unavailable) dims it.
      </p>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Status entity <span style={hint}>(sensor.* — "cooking" activates tile)</span></label>
        <EntityAutocomplete
          value={widget.entity_id ?? ''}
          onChange={(v) => onChange({ entity_id: v })}
          placeholder="sensor.sv_status"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Current temp entity <span style={hint}>(sensor.*)</span></label>
        <EntityAutocomplete
          value={widget.temp_entity ?? ''}
          onChange={(v) => onChange({ temp_entity: v })}
          placeholder="sensor.sv_temperature"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Target temp entity <span style={hint}>(sensor.*)</span></label>
        <EntityAutocomplete
          value={widget.target_entity ?? ''}
          onChange={(v) => onChange({ target_entity: v })}
          placeholder="sensor.sv_target_temperature"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Time remaining entity <span style={hint}>(minutes → HH:MM)</span></label>
        <EntityAutocomplete
          value={widget.time_entity ?? ''}
          onChange={(v) => onChange({ time_entity: v })}
          placeholder="sensor.sv_remaining_minutes"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Unit</label>
        <input
          type="text"
          value={widget.unit ?? '°C'}
          onChange={(e) => onChange({ unit: e.target.value })}
          placeholder="°C"
          style={{ ...inputStyle, width: 60 }}
        />
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const hint = { color: 'var(--ed-text-3)', fontWeight: 400 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
