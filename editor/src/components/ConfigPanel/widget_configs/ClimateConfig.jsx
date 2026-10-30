import { useState } from 'react';
import { HexColorPicker } from 'react-colorful';

const ALL_MODES = ['off', 'heat', 'cool', 'auto', 'fan_only', 'dry'];

export default function ClimateConfig({ widget, onChange }) {
  const modes = widget.modes ?? [];
  const state_formats = widget.state_formats ?? {};
  const [openPicker, setOpenPicker] = useState(null); // `${mode}_${field}`

  function toggleMode(mode) {
    const next = modes.includes(mode) ? modes.filter((m) => m !== mode) : [...modes, mode];
    onChange({ modes: next });
  }

  function setStateFormat(mode, field, value) {
    onChange({
      state_formats: {
        ...state_formats,
        [mode]: { ...(state_formats[mode] ?? {}), [field]: value },
      },
    });
  }

  function setTempStep(val) {
    if (val.trim() === '') return onChange({ temp_step: undefined });
    const v = parseFloat(val);
    if (Number.isFinite(v) && v > 0) onChange({ temp_step: v });
  }

  return (
    <div>
      <h3 style={sectionTitle}>Climate</h3>
      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Temperature step <span style={{ color: 'var(--ed-text-3)' }}>(blank = auto from entity)</span></label>
        <input
          key={widget.id}
          type="number"
          min={0.1}
          step={0.1}
          defaultValue={widget.temp_step ?? ''}
          onChange={(e) => setTempStep(e.target.value)}
          placeholder="auto"
          style={{ fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: 80, boxSizing: 'border-box' }}
        />
      </div>
      <label style={labelStyle}>Enabled modes</label>
      {ALL_MODES.map((m) => (
        <div key={m} style={{ marginBottom: 6 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <input type="checkbox" checked={modes.includes(m)} onChange={() => toggleMode(m)} />
            <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{m}</span>
          </label>
          {modes.includes(m) && (
            <div style={{ display: 'flex', gap: 8, marginTop: 4, paddingLeft: 22 }}>
              {['bgColor', 'textColor'].map((field) => {
                const pickerKey = `${m}_${field}`;
                const color = state_formats[m]?.[field] || '';
                return (
                  <div key={field} style={{ position: 'relative' }}>
                    <label style={{ fontSize: 10, color: 'var(--ed-text-3)', display: 'block', marginBottom: 2 }}>{field === 'bgColor' ? 'BG' : 'Text'}</label>
                    <button
                      onClick={() => setOpenPicker(openPicker === pickerKey ? null : pickerKey)}
                      style={{ width: 28, height: 28, borderRadius: 4, border: '1px solid var(--ed-border)', background: color || 'var(--ed-swatch-empty)', cursor: 'pointer' }}
                      title={color || 'not set'}
                    />
                    {openPicker === pickerKey && (
                      <div style={{ position: 'absolute', zIndex: 200, top: '100%', left: 0, background: 'var(--ed-surface)', border: '1px solid var(--ed-divider)', borderRadius: 8, boxShadow: 'var(--ed-popover-shadow)', padding: 8 }}>
                        <HexColorPicker color={color || '#ffffff'} onChange={(v) => setStateFormat(m, field, v)} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 4 };
