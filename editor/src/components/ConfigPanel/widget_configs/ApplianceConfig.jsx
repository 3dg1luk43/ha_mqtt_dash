import EntityAutocomplete from '../EntityAutocomplete';

export default function ApplianceConfig({ widget, onChange }) {
  return (
    <div>
      <h3 style={sectionTitle}>Appliance</h3>
      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 }}>
        <code>entity_id</code> drives running state — off / idle / standby / unavailable / unknown
        dims tile; any other value activates it.
      </p>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Running state entity <span style={hint}>(off/idle/standby/unavail = dim)</span></label>
        <EntityAutocomplete
          value={widget.entity_id ?? ''}
          onChange={(v) => onChange({ entity_id: v })}
          placeholder="sensor.washer_state"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Program entity <span style={hint}>(sensor.* — free text)</span></label>
        <EntityAutocomplete
          value={widget.program_entity ?? ''}
          onChange={(v) => onChange({ program_entity: v })}
          placeholder="sensor.washer_program"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Time remaining entity <span style={hint}>(minutes → HH:MM)</span></label>
        <EntityAutocomplete
          value={widget.time_entity ?? ''}
          onChange={(v) => onChange({ time_entity: v })}
          placeholder="sensor.washer_remaining_minutes"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Progress entity <span style={hint}>(0–100 % sensor, optional)</span></label>
        <EntityAutocomplete
          value={widget.progress_entity ?? ''}
          onChange={(v) => onChange({ progress_entity: v })}
          placeholder="sensor.washer_progress"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Phase entity <span style={hint}>(current phase / sub-state text, optional)</span></label>
        <EntityAutocomplete
          value={widget.phase_entity ?? ''}
          onChange={(v) => onChange({ phase_entity: v })}
          placeholder="sensor.washer_current_phase"
        />
      </div>
      <p style={{ fontSize: 10, color: 'var(--ed-text-3)', margin: 0, lineHeight: 1.4 }}>
        Left blank, HA auto-detects <code>&lt;prefix&gt;_progress</code> and{' '}
        <code>&lt;prefix&gt;_current_phase</code> siblings of the time remaining entity
        (e.g. <code>sensor.washer_progress</code> next to <code>sensor.washer_remaining_time</code>).
      </p>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const hint = { color: 'var(--ed-text-3)', fontWeight: 400 };
