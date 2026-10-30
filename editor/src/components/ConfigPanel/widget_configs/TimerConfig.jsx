function fmtSeconds(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m ${sec}s`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

// presets are stored as integer seconds; the UI edits them as minutes.
const fmtMinutes = (s) => String(Math.round((s / 60) * 100) / 100);

export default function TimerConfig({ widget, onChange }) {
  const secs = widget.default_seconds ?? 300;
  const presets = Array.isArray(widget.presets) ? widget.presets : [];

  function setPresetsFromText(text) {
    const vals = text.split(',').map((t) => parseFloat(t.trim()))
      .filter((m) => Number.isFinite(m) && m > 0)
      .map((m) => Math.max(1, Math.round(m * 60)));
    onChange({ presets: vals.length ? vals : undefined });
  }

  function num(val) {
    const v = parseInt(val, 10);
    return isNaN(v) || v < 1 ? 1 : v;
  }

  return (
    <div>
      <h3 style={sectionTitle}>Timer</h3>
      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 }}>
        Local countdown — no entity or MQTT required. State (running/paused) persists
        across page switches and profile reloads via the widget <code>id</code>.
      </p>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Default duration (seconds)</label>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            type="number"
            min={1}
            value={secs}
            onChange={(e) => onChange({ default_seconds: num(e.target.value) })}
            style={{ ...inputStyle, width: 80 }}
          />
          <span style={{ fontSize: 12, color: 'var(--ed-text-3)' }}>= {fmtSeconds(secs)}</span>
        </div>
      </div>

      {/* Quick-set presets */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {[[30,'30s'],[60,'1m'],[180,'3m'],[300,'5m'],[600,'10m'],[900,'15m'],[1800,'30m'],[3600,'1h']].map(([v, lbl]) => (
          <button
            key={v}
            onClick={() => onChange({ default_seconds: v })}
            style={{
              fontSize: 11,
              padding: '2px 8px',
              border: '1px solid var(--ed-border)',
              borderRadius: 3,
              background: secs === v ? 'var(--ed-primary)' : 'var(--ed-surface-2)',
              color: secs === v ? 'var(--ed-on-primary)' : 'var(--ed-text-2)',
              cursor: 'pointer',
            }}
          >
            {lbl}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 10 }}>
        <label style={labelStyle}>Quick-pick presets — minutes, comma-separated (saved as seconds)</label>
        <input
          key={widget.id}
          type="text"
          defaultValue={presets.map(fmtMinutes).join(', ')}
          onBlur={(e) => setPresetsFromText(e.target.value)}
          placeholder="1, 3, 5, 10 (blank = device defaults)"
          style={{ ...inputStyle, width: '100%' }}
        />
        <p style={{ fontSize: 10, color: 'var(--ed-text-3)', margin: '2px 0 0' }}>
          {presets.length
            ? <>Exported as <code>presets: [{presets.join(', ')}]</code> seconds</>
            : 'Blank uses the device default chips'}
        </p>
      </div>

      <div style={{ marginTop: 10 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--ed-text-2)', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={widget.configurable !== false}
            onChange={(e) => onChange({ configurable: e.target.checked ? undefined : false })}
          />
          Allow changing the duration on the tile
        </label>
        <p style={{ fontSize: 10, color: 'var(--ed-text-3)', margin: '2px 0 0 20px' }}>
          Uncheck to lock the duration (hides the set / adjust controls)
        </p>
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', boxSizing: 'border-box' };
