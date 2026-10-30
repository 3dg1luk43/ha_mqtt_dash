import EntityAutocomplete from '../EntityAutocomplete';

const ENTITY_FIELDS = [
  { key: 'nozzle_entity', label: 'Nozzle temp entity', ph: 'sensor.printer_nozzle_temp' },
  { key: 'nozzle_target_entity', label: 'Nozzle target entity', hint: '(optional)', ph: 'sensor.printer_nozzle_target' },
  { key: 'bed_entity', label: 'Bed temp entity', ph: 'sensor.printer_bed_temp' },
  { key: 'bed_target_entity', label: 'Bed target entity', hint: '(optional)', ph: 'sensor.printer_bed_target' },
  { key: 'time_entity', label: 'Print time entity', ph: 'sensor.printer_time_left' },
  { key: 'progress_entity', label: 'Progress entity', ph: 'sensor.printer_progress' },
  { key: 'status_entity', label: 'Status entity', ph: 'sensor.printer_status' },
  { key: 'preview_entity', label: 'Preview image entity', hint: '(image.* — current print thumbnail)', ph: 'image.printer_current_print' },
  { key: 'layer_entity', label: 'Current layer entity', hint: '(optional)', ph: 'sensor.printer_current_layer' },
  { key: 'total_layers_entity', label: 'Total layers entity', hint: '(optional)', ph: 'sensor.printer_total_layers' },
];

// Rows the device can show. 'preview' and 'layer' need their entities set.
const ALL_ROWS = ['nozzle', 'bed', 'time', 'progress', 'status', 'preview', 'layer'];

export default function PrinterConfig({ widget, onChange }) {
  const visible = widget.visible_rows ?? ALL_ROWS;

  function toggleRow(row) {
    const next = visible.includes(row)
      ? visible.filter((r) => r !== row)
      : [...visible, row];
    onChange({ visible_rows: next });
  }

  function moveRow(row, delta) {
    const idx = visible.indexOf(row);
    const next = [...visible];
    const target = idx + delta;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    onChange({ visible_rows: next });
  }

  const unchecked = ALL_ROWS.filter(r => !visible.includes(r));

  return (
    <div>
      <h3 style={sectionTitle}>3D Printer</h3>

      {ENTITY_FIELDS.map(({ key, label, hint, ph }) => (
        <div key={key} style={{ marginBottom: 6 }}>
          <label style={labelStyle}>{label}{hint && <span style={{ color: 'var(--ed-text-3)', fontWeight: 400 }}> {hint}</span>}</label>
          <EntityAutocomplete
            value={widget[key] ?? ''}
            onChange={(v) => onChange({ [key]: v })}
            placeholder={ph}
          />
        </div>
      ))}

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Progress unit</label>
        <input
          type="text"
          value={widget.progress_unit ?? ''}
          onChange={(e) => onChange({ progress_unit: e.target.value })}
          placeholder="e.g. %"
          style={{ ...inputStyle, width: 64 }}
        />
      </div>

      <div>
        <label style={labelStyle}>Visible rows <span style={{ color: 'var(--ed-text-3)', fontWeight: 400 }}>(drag order = display order)</span></label>

        {/* Visible rows — ordered, with move buttons */}
        {visible.map((r, i) => (
          <div key={r} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
            <button onClick={() => moveRow(r, -1)} disabled={i === 0} style={arrowBtn}>↑</button>
            <button onClick={() => moveRow(r, 1)} disabled={i === visible.length - 1} style={arrowBtn}>↓</button>
            <span style={{ flex: 1, fontSize: 12, textTransform: 'capitalize', color: 'var(--ed-text)' }}>{r}</span>
            <button onClick={() => toggleRow(r)} style={removeBtn} title="Remove">×</button>
          </div>
        ))}

        {/* Hidden rows — add back */}
        {unchecked.length > 0 && (
          <div style={{ marginTop: 4, borderTop: '1px solid var(--ed-divider-2)', paddingTop: 4 }}>
            {unchecked.map(r => (
              <div key={r} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                <span style={{ width: 34 }} />
                <span style={{ flex: 1, fontSize: 12, textTransform: 'capitalize', color: 'var(--ed-text-3)' }}>{r}</span>
                <button onClick={() => toggleRow(r)} style={addBtn} title="Add">+</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 4 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box' };
const arrowBtn = { padding: '1px 5px', fontSize: 11, border: '1px solid var(--ed-border)', borderRadius: 3, background: 'var(--ed-surface-2)', cursor: 'pointer', lineHeight: 1.4 };
const removeBtn = { padding: '1px 6px', fontSize: 13, border: 'none', background: 'none', cursor: 'pointer', color: 'var(--ed-text-3)', lineHeight: 1 };
const addBtn = { padding: '1px 6px', fontSize: 13, border: '1px solid var(--ed-border)', borderRadius: 3, background: 'var(--ed-surface-2)', cursor: 'pointer', color: 'var(--ed-text-3)', lineHeight: 1.4 };
