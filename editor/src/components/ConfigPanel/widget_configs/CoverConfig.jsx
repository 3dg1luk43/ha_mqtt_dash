import EntityAutocomplete from '../EntityAutocomplete';

// All individually-selectable cover controls (token -> label).
const ALL_ITEMS = [
  ['open', 'Open ▲'],
  ['close', 'Close ▼'],
  ['stop', 'Stop ■'],
  ['position', 'Position slider'],
  ['presets', 'Position presets'],
  ['tilt_open', 'Tilt open'],
  ['tilt_close', 'Tilt close'],
  ['tilt_slider', 'Tilt slider'],
];
const LABELS = Object.fromEntries(ALL_ITEMS);
const DEFAULT_PRESETS = [0, 25, 75, 100];

// Expand the legacy coarse groups into granular tokens (for migrating old widgets).
function expandGroups(groups) {
  const out = [];
  for (const g of groups || []) {
    if (g === 'buttons') out.push('open', 'stop', 'close');
    else if (g === 'slider') out.push('position');
    else if (g === 'presets') out.push('presets');
    else if (g === 'tilt') out.push('tilt_open', 'tilt_close', 'tilt_slider');
  }
  return out;
}

export default function CoverConfig({ widget, onChange }) {
  const items = Array.isArray(widget.cover_items) && widget.cover_items.length
    ? widget.cover_items
    : (Array.isArray(widget.cover_controls) ? expandGroups(widget.cover_controls) : []);
  const layout = widget.cover_layout || 'auto';
  const presets = Array.isArray(widget.position_presets) ? widget.position_presets : DEFAULT_PRESETS;
  const enabled = new Set(items);
  const available = ALL_ITEMS.filter(([k]) => !enabled.has(k));

  // Writing always migrates to cover_items and drops the legacy cover_controls key.
  const setItems = (next) => onChange({ cover_items: next, cover_controls: undefined });
  const add = (k) => setItems([...items, k]);
  const remove = (k) => setItems(items.filter((x) => x !== k));
  const move = (i, d) => {
    const j = i + d;
    if (j < 0 || j >= items.length) return;
    const next = items.slice();
    [next[i], next[j]] = [next[j], next[i]];
    setItems(next);
  };
  const setPresetsFromText = (text) => {
    const vals = text.split(',').map((s) => parseInt(s.trim(), 10))
      .filter((n) => Number.isFinite(n)).map((n) => Math.max(0, Math.min(100, n)));
    onChange({ position_presets: vals });
  };

  return (
    <div>
      <h3 style={sectionTitle}>Cover</h3>
      <p style={hint}>
        Binds to a <code>cover.*</code> entity. Pick the controls to show and order them
        (top→bottom in tall tiles, row sequence in wide tiles). Leave the list empty to
        <strong> auto-detect</strong> from the cover&apos;s <code>supported_features</code>.
        The entity must be in <code>mirror_entities</code> (or use auto-mirror).
      </p>

      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Cover entity</label>
        <EntityAutocomplete
          value={widget.entity_id ?? ''}
          onChange={(v) => onChange({ entity_id: v })}
          placeholder="cover.bedroom_blinds"
        />
      </div>

      <label style={labelStyle}>Controls &amp; order</label>
      {items.length === 0 && (
        <p style={{ ...hint, color: 'var(--ed-text-3)' }}>No controls selected — the app auto-detects from the entity.</p>
      )}
      <div style={{ marginBottom: 8 }}>
        {items.map((k, i) => (
          <div key={k} style={rowStyle}>
            <span style={{ flex: 1, fontSize: 12, color: 'var(--ed-text)' }}>{LABELS[k] || k}</span>
            <button type="button" style={iconBtn} disabled={i === 0} onClick={() => move(i, -1)} title="Move up">↑</button>
            <button type="button" style={iconBtn} disabled={i === items.length - 1} onClick={() => move(i, 1)} title="Move down">↓</button>
            <button type="button" style={{ ...iconBtn, color: 'var(--ed-error)' }} onClick={() => remove(k)} title="Remove">✕</button>
          </div>
        ))}
      </div>

      {available.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <label style={labelStyle}>Add control</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {available.map(([k, lbl]) => (
              <button type="button" key={k} style={addBtn} onClick={() => add(k)}>+ {lbl}</button>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Layout</label>
        <select value={layout} onChange={(e) => onChange({ cover_layout: e.target.value })} style={selectStyle}>
          <option value="auto">Auto (from tile shape)</option>
          <option value="horizontal">Horizontal (rows)</option>
          <option value="vertical">Vertical (upright sliders)</option>
        </select>
      </div>

      {enabled.has('presets') && (
        <div style={{ marginBottom: 8 }}>
          <label style={labelStyle}>Position presets (%)</label>
          <input
            type="text"
            defaultValue={presets.join(', ')}
            onBlur={(e) => setPresetsFromText(e.target.value)}
            placeholder="0, 25, 75, 100"
            style={inputStyle}
          />
        </div>
      )}
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const hint = { fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
const rowStyle = { display: 'flex', alignItems: 'center', gap: 4, padding: '3px 4px', marginBottom: 3, background: 'var(--ed-surface-2)', borderRadius: 4 };
const iconBtn = { width: 22, height: 22, border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-surface)', color: 'var(--ed-text)', cursor: 'pointer', fontSize: 12, lineHeight: 1, padding: 0 };
const addBtn = { border: '1px dashed var(--ed-text-3)', borderRadius: 4, background: 'var(--ed-input-bg)', cursor: 'pointer', fontSize: 11, padding: '3px 7px', color: 'var(--ed-text-2)' };
const selectStyle = { width: '100%', padding: '5px 6px', fontSize: 12, border: '1px solid var(--ed-border)', borderRadius: 4, boxSizing: 'border-box' };
const inputStyle = { width: '100%', padding: '5px 6px', fontSize: 12, border: '1px solid var(--ed-border)', borderRadius: 4, boxSizing: 'border-box' };
