import EntityAutocomplete from '../EntityAutocomplete';

export default function MediaPlayerConfig({ widget, onChange }) {
  return (
    <div>
      <h3 style={sectionTitle}>Media Player</h3>
      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 }}>
        Binds to a <code>media_player.*</code> entity. Displays song title, artist,
        play/pause, next/previous controls, and a seekable progress bar. The entity must
        be in <code>mirror_entities</code> (or use auto-mirror).
      </p>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Media player entity</label>
        <EntityAutocomplete
          value={widget.entity_id ?? ''}
          onChange={(v) => onChange({ entity_id: v })}
          placeholder="media_player.living_room"
        />
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--ed-text-2)', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={widget.show_art !== false}
          onChange={(e) => onChange({ show_art: e.target.checked ? undefined : false })}
        />
        Show album art
      </label>
      <p style={{ fontSize: 10, color: 'var(--ed-text-3)', margin: '2px 0 0 20px', lineHeight: 1.4 }}>
        HA fetches the artwork automatically — no URL needed. Shown beside the controls on wide
        tiles, as a dimmed background on narrow ones.
      </p>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 8px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const labelStyle = { fontSize: 11, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 };
