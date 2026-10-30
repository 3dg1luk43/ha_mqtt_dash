export default function LightConfig({ widget, onChange }) {
  // Absent = auto-detect from the light's supported_color_modes; only false is meaningful.
  const dimmable = widget.dimmable !== false;

  return (
    <div>
      <h3 style={sectionTitle}>Light</h3>
      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 10, lineHeight: 1.4 }}>
        Tap toggles on/off; drag on the tile to change brightness. The device detects whether
        the light is dimmable from its <code>supported_color_modes</code>.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, gap: 8 }}>
        <label style={{ fontSize: 12, color: 'var(--ed-text-2)', flexShrink: 0, minWidth: 70 }}>Dimmable</label>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="checkbox"
            checked={dimmable}
            onChange={(e) => onChange({ dimmable: e.target.checked ? undefined : false })}
            style={{ width: 16, height: 16 }}
          />
          <span style={{ fontSize: 11, color: 'var(--ed-text-3)' }}>
            {dimmable ? 'Auto (brightness if the light supports it)' : 'Forced on/off only'}
          </span>
        </div>
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 10px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
