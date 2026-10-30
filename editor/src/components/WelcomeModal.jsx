import { useState } from 'react';
import { EMBEDDED } from '../utils/haEmbed';

// Declared before STEPS: its JSX is built at module load
const p = { fontSize: 13, color: 'var(--ed-text)', lineHeight: 1.6, margin: '0 0 12px' };
const disclaimerBox = { background: 'var(--ed-primary-soft)', border: '1px solid var(--ed-info-border)', borderRadius: 6, padding: '10px 12px', marginTop: 4 };
const featureCard = { background: 'var(--ed-info-bg)', border: '1px solid var(--ed-info-border)', borderRadius: 6, padding: '10px 10px', display: 'flex', flexDirection: 'column', gap: 4 };
const tipBox = { background: 'var(--ed-note-bg)', border: '1px solid var(--ed-note-border)', borderRadius: 5, padding: '7px 10px', fontSize: 12, color: 'var(--ed-warn-text)', marginTop: 10 };
const code = { background: 'var(--ed-surface-2)', borderRadius: 3, padding: '1px 4px', fontFamily: 'monospace', fontSize: 12 };

const STEPS = [
  {
    title: 'Welcome to MQTTDash Profile Editor',
    content: (
      <div>
        <p style={p}>
          A visual drag-and-drop editor for building <strong>Home Assistant MQTTDash</strong> dashboard profiles.{' '}
          {EMBEDDED
            ? <>Design your tablet layout here and push it to your wall panel with <strong>⚡ Deploy</strong>.</>
            : 'Design your tablet layout here, export the JSON, and paste it straight into HA.'}
        </p>

        {EMBEDDED ? (
          <div style={disclaimerBox}>
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6, color: 'var(--ed-primary)' }}>
              🏠 Running inside Home Assistant
            </div>
            <p style={{ ...p, margin: 0, color: 'var(--ed-text)' }}>
              The editor uses this Home Assistant session — no extra login or token. Work in progress is kept in
              this browser's <strong>localStorage</strong>; <strong>⚡ Deploy</strong> stores it on the selected panel.
            </p>
          </div>
        ) : (
        <div style={disclaimerBox}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6, color: 'var(--ed-primary)' }}>
            🔒 Privacy — no backend, no tracking
          </div>
          <p style={{ ...p, margin: 0, color: 'var(--ed-text)' }}>
            Everything runs <strong>entirely in your browser</strong>. No data is sent anywhere.
            Your widgets, grid settings, and entity list are saved to your browser's{' '}
            <strong>localStorage</strong> only — clearing browser data will erase them.
            Use <strong>Export → Download .json</strong> to back up your work.
          </p>
        </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
          {[
            ['🖱️', 'Drag & drop', 'Drag widget types onto the canvas. Move and resize freely.'],
            ['📱', 'Real resolution', 'Previews at actual device pixel dimensions — Retina included.'],
            ['⚙️', 'Full config', 'Per-widget properties, colors, entity IDs, and format options.'],
            EMBEDDED
              ? ['⚡', 'Deploy', 'Pick a panel in the toolbar and deploy the layout with one click.']
              : ['⬇️', 'Export to HA', 'One-click JSON export ready for mqtt_dash.set_device_profile.'],
          ].map(([icon, title, desc]) => (
            <div key={title} style={featureCard}>
              <div style={{ fontSize: 20 }}>{icon}</div>
              <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--ed-text)' }}>{title}</div>
              <div style={{ fontSize: 11, color: 'var(--ed-text-2)', lineHeight: 1.4 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    title: '1 — Select your device & orientation',
    content: (
      <div>
        <img src={null} alt="" style={{ display: 'none' }} />
        <p style={p}>
          Use the <strong>{EMBEDDED ? 'device picker in the toolbar' : 'toolbar below the header'}</strong> to choose your iPad model. The canvas immediately
          updates to that device's physical pixel resolution — 768×1024 for 1× models,
          1536×2048 for Retina 2× models.
        </p>
        <StepBox icon="▯ / ▭" label="Portrait / Landscape toggle">
          Switch orientation at any time. Cell widths auto-recalculate to fill the new screen width.
        </StepBox>
        <StepBox icon="Custom" label="Custom resolution">
          Pick <strong>Custom</strong> in the dropdown and enter any W×H pixel dimensions — useful for
          non-standard screens.
        </StepBox>
        <StepBox icon="⚙ Grid (Config Panel)" label="Grid settings">
          Adjust <strong>columns</strong>, cell width & height (cells don't have to be squares), and margins.
          The <strong>↔ Fill</strong> button resets cell width to perfectly divide the screen.
        </StepBox>
      </div>
    ),
  },
  {
    title: '2 — Add & arrange widgets',
    content: (
      <div>
        <p style={p}>
          The <strong>Widget Library</strong> on the left lists all 13 supported widget types.
          Drag any widget from the palette onto the iPad canvas — it snaps to the nearest grid cell.
        </p>
        <StepBox icon="🖱️" label="Drag to place">
          Drag from the palette onto the canvas. The grid overlay shows cell boundaries as you hover.
        </StepBox>
        <StepBox icon="↔↕" label="Resize">
          Grab the <strong>bottom-right handle</strong> on any placed widget and drag to resize in whole-cell increments.
        </StepBox>
        <StepBox icon="✕" label="Delete">
          Hover a widget and click the <strong>× button</strong> in the top-right corner to remove it.
        </StepBox>
        <StepBox icon="🔴" label="Overlap warning">
          Widgets with a <strong>red border</strong> overlap another widget — fix by moving or resizing.
        </StepBox>
        <div style={tipBox}>
          <strong>Ctrl+Z</strong> undoes the last action. <strong>Ctrl+Y</strong> redoes it. Up to 50 steps.
        </div>
      </div>
    ),
  },
  {
    title: '3 — Configure widgets',
    content: (
      <div>
        <p style={p}>
          <strong>Click any widget</strong> on the canvas to select it. The right panel switches to that
          widget's configuration.
        </p>
        <StepBox icon="ID" label="Common fields">
          Set the widget <strong>ID</strong> (used in HA), display <strong>label</strong>,{' '}
          <strong>entity ID</strong>, grid position (x/y/w/h), and whether it's <em>protected</em>{' '}
          (requires long-press to activate).
        </StepBox>
        <StepBox icon="🎨" label="Format">
          Control horizontal and vertical text alignment, text size, and up to 6 colors
          (text, background, on/off variants). Click the color swatch to open an inline picker.
        </StepBox>
        <StepBox icon="🔧" label="Type-specific options">
          Each widget type shows only its own extra fields — e.g. Weather shows attribute
          checkboxes, Climate shows mode toggles with per-state colors, Camera shows stream URL.
        </StepBox>
        <div style={tipBox}>
          Click an empty area of the canvas to deselect — the right panel shows grid settings.
        </div>
      </div>
    ),
  },
  {
    title: '4 — Entity list & autocomplete',
    content: (
      <div>
        <p style={p}>
          Build a personal list of your Home Assistant entity IDs. These appear as autocomplete
          suggestions on every entity field in the editor — no connection to HA required.
        </p>
        <StepBox icon="🗂" label="Open the Entities tab">
          Click on an empty area of the canvas, then in the right panel click the{' '}
          <strong>Entities</strong> tab.
        </StepBox>
        {EMBEDDED ? (
          <StepBox icon="⟳" label="Synced from Home Assistant">
            Inside Home Assistant the list is filled automatically with all your entities when the editor opens.
          </StepBox>
        ) : (
        <StepBox icon="📋" label="Bulk add (recommended)">
          In HA, go to <strong>Developer Tools → States</strong>, select all entity IDs, copy and paste
          them into the <strong>Bulk add</strong> tab. One entity per line or comma-separated — the
          editor de-duplicates automatically.
        </StepBox>
        )}
        <StepBox icon="🔤" label="Autocomplete">
          Once entities are in your list, any entity ID input shows matching suggestions as you type.
          Entities are grouped by domain (light, switch, sensor…).
        </StepBox>
        <div style={tipBox}>
          Your entity list is saved to localStorage and persists across page refreshes.
        </div>
      </div>
    ),
  },
  EMBEDDED ? {
    title: '5 — Deploy to your panel',
    content: (
      <div>
        <p style={p}>
          Pick the wall panel in the <strong>toolbar</strong> (left). The editor deploys to and loads from that panel.
        </p>
        <StepBox icon="⤓" label="Load">
          Replaces the canvas with the profile the panel is using right now — a good starting point.
        </StepBox>
        <StepBox icon="⚡" label="Deploy">
          Sends the current layout to the selected panel. It updates immediately.
        </StepBox>
        <StepBox icon="⬇" label="Export / Import">
          Copy, download or share the profile JSON for backups, and load it back with <strong>Import</strong>.
          The export dialog also lists the entities the layout uses (<strong>HA Mirror entities</strong>).
        </StepBox>
      </div>
    ),
  } : {
    title: '5 — Export & apply to HA',
    content: (
      <div>
        <p style={p}>
          When your layout is ready, click <strong>Export</strong> in the header.
        </p>
        <StepBox icon="📋" label="Copy or download">
          Use <strong>Copy JSON</strong> to copy to clipboard, or <strong>Download .json</strong> to save a file.
          The JSON is in the flat format accepted by the HA integration.
        </StepBox>
        <StepBox icon="⬇️" label="Apply in Home Assistant">
          In HA go to <strong>Developer Tools → Services</strong>, call{' '}
          <code style={code}>mqtt_dash.set_device_profile</code> and paste the JSON as the{' '}
          <code style={code}>profile</code> field. The tablet updates immediately.
        </StepBox>
        <StepBox icon="🔗" label="Mirror entities checklist">
          Below the JSON preview, the export modal lists every entity ID used in your profile
          under <strong>HA Mirror entities</strong>. Add these to the integration's mirror
          configuration so their states are published over MQTT.
          This list is <em>not</em> included in the exported JSON — it's a reference only.
        </StepBox>
        <div style={tipBox}>
          Use <strong>Import</strong> to reload a saved profile back into the editor at any time.
        </div>
      </div>
    ),
  },
];

export default function WelcomeModal({ onClose }) {
  const [step, setStep] = useState(0);
  const isLast = step === STEPS.length - 1;

  return (
    <div style={overlay}>
      <div style={modal}>
        {/* Progress dots */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 6, marginBottom: 20 }}>
          {STEPS.map((_, i) => (
            <button
              key={i}
              onClick={() => setStep(i)}
              style={{
                width: i === step ? 20 : 8,
                height: 8,
                borderRadius: 4,
                border: 'none',
                background: i === step ? 'var(--ed-primary)' : 'var(--ed-border)',
                cursor: 'pointer',
                padding: 0,
                transition: 'width 0.2s, background 0.2s',
              }}
            />
          ))}
        </div>

        {/* Step content */}
        <div style={{ minHeight: 340 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, margin: '0 0 14px', color: 'var(--ed-primary)' }}>
            {STEPS[step].title}
          </h2>
          {STEPS[step].content}
        </div>

        {/* Navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--ed-divider-2)' }}>
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            style={navBtn(false, step === 0)}
          >
            ← Back
          </button>

          <span style={{ fontSize: 11, color: 'var(--ed-text-3)' }}>{step + 1} / {STEPS.length}</span>

          {isLast ? (
            <button onClick={onClose} style={navBtn(true, false)}>
              Get started →
            </button>
          ) : (
            <button onClick={() => setStep((s) => s + 1)} style={navBtn(true, false)}>
              Next →
            </button>
          )}
        </div>

        {/* Skip */}
        {!isLast && (
          <div style={{ textAlign: 'center', marginTop: 10 }}>
            <button onClick={onClose} style={{ border: 'none', background: 'none', fontSize: 12, color: 'var(--ed-text-3)', cursor: 'pointer' }}>
              Skip tutorial
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function StepBox({ icon, label, children }) {
  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 10, padding: '8px 10px', background: 'var(--ed-info-bg)', borderRadius: 6, border: '1px solid var(--ed-info-border)' }}>
      <div style={{ fontSize: 16, flexShrink: 0, width: 24, textAlign: 'center', marginTop: 1 }}>{icon}</div>
      <div>
        <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--ed-text)', marginBottom: 2 }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--ed-text-2)', lineHeight: 1.5 }}>{children}</div>
      </div>
    </div>
  );
}

const overlay = { position: 'fixed', inset: 0, background: EMBEDDED ? 'var(--ed-overlay)' : 'rgba(10,15,40,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 };
const modal = { background: 'var(--ed-surface)', color: 'var(--ed-text)', border: EMBEDDED ? '1px solid var(--ed-divider)' : 'none', borderRadius: EMBEDDED ? 'var(--ed-radius)' : 12, padding: 28, width: 540, maxWidth: '92vw', maxHeight: '92vh', overflow: 'auto', boxShadow: EMBEDDED ? 'var(--ed-shadow)' : '0 12px 48px rgba(0,0,0,0.25)' };
function navBtn(primary, disabled) {
  return {
    padding: '7px 18px', fontSize: 13, fontWeight: 600, borderRadius: 6, border: 'none',
    background: disabled ? 'var(--ed-divider-2)' : primary ? 'var(--ed-primary)' : 'var(--ed-divider-2)',
    color: disabled ? 'var(--ed-text-3)' : primary ? 'var(--ed-on-primary)' : 'var(--ed-text)',
    cursor: disabled ? 'default' : 'pointer',
  };
}
