import { useState } from 'react';
import { HexColorPicker } from 'react-colorful';
import { useEditorStore, effectiveGrid } from '../../store/editorStore';
import { NAV_H, NAV_W } from '../../utils/frameGeometry';

const NAVBAR_EDGES = ['top', 'bottom', 'left', 'right'];

const NAV_STYLE_FIELDS = [
  { key: 'bgColor',       label: 'Bar background',  placeholder: '#141414' },
  { key: 'activeColor',   label: 'Active tab',       placeholder: '#336ee6' },
  { key: 'inactiveColor', label: 'Inactive tab',     placeholder: '#404040' },
  { key: 'textColor',     label: 'Tab text',         placeholder: '#ffffff' },
  { key: 'borderColor',   label: 'Border',           placeholder: 'rgba(255,255,255,0.18)' },
];

export default function GridConfigSection() {
  const { grid, banner, setBanner, setGridConfig, setPageGrid, setNavbarEdge, setNavbarStyle, navbar_edge, navbar_style = {}, navbar_show_battery = true, navbar_show_keepawake = true, setNavbarShowBattery, setNavbarShowKeepAwake, device_settings = {}, setDeviceSettings, device, orientation, pages, activePageIndex } = useEditorStore();
  const [navStyleOpen, setNavStyleOpen] = useState(false);
  const [openPicker, setOpenPicker] = useState(null);

  const activePage = pages[activePageIndex];
  const hasPageOverride = !!activePage?.grid;
  // The grid being edited: page override if active, else top-level
  const displayGrid = effectiveGrid(grid, activePage);

  const [pw, ph] = device.points ?? [768, 1024];
  const [screenW, screenH] = orientation === 'landscape' ? [ph, pw] : [pw, ph];

  // Subtract nav bar from usable content area
  const navIsVertical = navbar_edge === 'left' || navbar_edge === 'right';
  const contentW = navIsVertical ? screenW - NAV_W : screenW;
  const contentH = navIsVertical ? screenH : screenH - NAV_H;

  const autoW = Math.floor(contentW / displayGrid.columns);
  const colsFit = Math.floor(contentW / displayGrid.widget_dimensions[0]);
  const rowsFit = Math.floor(contentH / displayGrid.widget_dimensions[1]);

  // Detect overflow: any widget whose right/bottom edge exceeds content area
  const activeWidgets = activePage?.widgets ?? [];
  const cellW = displayGrid.widget_dimensions[0];
  const cellH = displayGrid.widget_dimensions[1];
  const overflowX = activeWidgets.some((w) => (w.x + w.w) * cellW > contentW);
  const overflowY = activeWidgets.some((w) => (w.y + w.h) * cellH > contentH);
  const hasOverflow = overflowX || overflowY;

  function fitToScreen() {
    // Compute cell size so all columns fit in contentW, and all used rows fit in contentH
    const maxRow = activeWidgets.reduce((m, w) => Math.max(m, w.y + w.h), displayGrid.columns);
    const fitW = Math.floor(contentW / displayGrid.columns);
    const fitH = Math.floor(contentH / maxRow);
    patchGrid({ widget_dimensions: [fitW, fitH] });
  }

  function num(val, fallback = 0) {
    const v = parseInt(val, 10);
    return isNaN(v) ? fallback : v;
  }

  function patchGrid(patch) {
    if (hasPageOverride) setPageGrid(activePageIndex, patch);
    else setGridConfig(patch);
  }

  function enablePageOverride() {
    // Copy top-level grid as page override
    setPageGrid(activePageIndex, { ...grid });
  }

  function disablePageOverride() {
    setPageGrid(activePageIndex, null);
  }

  return (
    <div>
      <h3 style={sectionTitle}>Grid Settings</h3>

      {/* Screen info */}
      <div style={{ background: 'var(--ed-info-bg)', borderRadius: 5, padding: '6px 8px', marginBottom: 8, fontSize: 11, color: 'var(--ed-text)' }}>
        Content area: <strong>{contentW}×{contentH}pt</strong>
        {navbar_edge !== 'none' && <span style={{ color: 'var(--ed-text-3)' }}> (nav {navIsVertical ? `−${NAV_W}pt wide` : `−${NAV_H}pt tall`})</span>}
        <br />
        <strong>{colsFit} cols × {rowsFit} rows</strong> fit at current cell size
      </div>

      {/* Overflow warning + auto-fit */}
      {hasOverflow && (
        <div style={{ background: 'var(--ed-warn-bg)', border: '1px solid var(--ed-warn-border)', borderRadius: 5, padding: '6px 8px', marginBottom: 8, fontSize: 11, color: 'var(--ed-warn-text)' }}>
          ⚠ Widgets overflow the {overflowX && overflowY ? 'right and bottom edges' : overflowX ? 'right edge' : 'bottom edge'}.
          <button
            onClick={fitToScreen}
            style={{ display: 'block', marginTop: 5, width: '100%', fontSize: 11, padding: '4px 0', border: '1px solid var(--ed-warn-border)', borderRadius: 4, background: 'var(--ed-warning)', color: 'var(--ed-on-warning)', cursor: 'pointer', fontWeight: 600 }}
          >
            ↔↕ Auto-fit cells to screen
          </button>
        </div>
      )}

      {/* Page grid override toggle */}
      <div style={{ background: hasPageOverride ? 'var(--ed-note-bg)' : 'var(--ed-surface-2)', border: `1px solid ${hasPageOverride ? 'var(--ed-note-border)' : 'var(--ed-divider-2)'}`, borderRadius: 5, padding: '6px 8px', marginBottom: 10 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={hasPageOverride}
            onChange={(e) => e.target.checked ? enablePageOverride() : disablePageOverride()}
          />
          <span>
            <strong>Override grid for "{activePage?.name}"</strong>
            {hasPageOverride
              ? ' — changes below affect this page only'
              : ' — changes below affect all pages'}
          </span>
        </label>
      </div>

      <Field label="Navbar edge">
        <div style={{ display: 'flex', gap: 3 }}>
          {NAVBAR_EDGES.map((edge) => (
            <button
              key={edge}
              onClick={() => setNavbarEdge(edge)}
              style={{
                fontSize: 11, padding: '3px 7px', border: '1px solid var(--ed-border)', borderRadius: 4,
                background: navbar_edge === edge ? 'var(--ed-primary)' : 'var(--ed-surface-2)',
                color: navbar_edge === edge ? 'var(--ed-on-primary)' : 'var(--ed-text-2)',
                cursor: 'pointer', textTransform: 'capitalize',
              }}
            >
              {edge}
            </button>
          ))}
        </div>
      </Field>

      <Field label="Keep-awake button">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={navbar_show_keepawake}
            onChange={(e) => setNavbarShowKeepAwake(e.target.checked)}
          />
          <span style={{ fontSize: 11, color: 'var(--ed-text-2)' }}>Show in nav bar</span>
        </label>
      </Field>

      <Field label="Battery indicator">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={navbar_show_battery}
            onChange={(e) => setNavbarShowBattery(e.target.checked)}
          />
          <span style={{ fontSize: 11, color: 'var(--ed-text-2)' }}>Show in nav bar</span>
        </label>
      </Field>

      {/* Nav bar style colors */}
      <div style={{ marginBottom: 10 }}>
        <button
          onClick={() => setNavStyleOpen(!navStyleOpen)}
          style={{ width: '100%', textAlign: 'left', background: navStyleOpen ? 'var(--ed-primary-soft)' : 'var(--ed-surface-2)', border: '1px solid var(--ed-border)', borderRadius: 4, padding: '4px 8px', fontSize: 12, cursor: 'pointer', fontWeight: 600, color: 'var(--ed-text)' }}
        >
          {navStyleOpen ? '▾' : '▸'} Nav bar colors
          {Object.keys(navbar_style).length > 0 && <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--ed-text-3)' }}>(custom)</span>}
        </button>
        {navStyleOpen && (
          <div style={{ marginTop: 6, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {NAV_STYLE_FIELDS.map(({ key, label, placeholder }) => {
              const val = navbar_style[key] || '';
              return (
                <div key={key} style={{ position: 'relative' }}>
                  <label style={{ fontSize: 10, color: 'var(--ed-text-2)', display: 'block', marginBottom: 2 }}>{label}</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                    <button
                      onClick={() => setOpenPicker(openPicker === key ? null : key)}
                      style={{ width: 20, height: 20, borderRadius: 3, border: '1px solid var(--ed-border)', background: val || 'var(--ed-swatch-empty)', cursor: 'pointer', flexShrink: 0 }}
                      title={val || placeholder}
                    />
                    <input
                      type="text"
                      value={val}
                      onChange={(e) => setNavbarStyle({ [key]: e.target.value || undefined })}
                      placeholder={placeholder}
                      style={{ fontSize: 10, padding: '2px 4px', border: '1px solid var(--ed-border)', borderRadius: 3, width: '100%', boxSizing: 'border-box' }}
                    />
                    {val && (
                      <button onClick={() => setNavbarStyle({ [key]: undefined })} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--ed-text-3)', fontSize: 13, padding: 0, lineHeight: 1, flexShrink: 0 }}>×</button>
                    )}
                  </div>
                  {openPicker === key && (
                    <div style={{ position: 'absolute', zIndex: 200, top: '100%', left: 0, background: 'var(--ed-surface)', border: '1px solid var(--ed-divider)', borderRadius: 8, boxShadow: 'var(--ed-popover-shadow)', padding: 8 }}>
                      <HexColorPicker color={val || '#ffffff'} onChange={(c) => setNavbarStyle({ [key]: c })} />
                      <button onClick={() => { setNavbarStyle({ [key]: undefined }); setOpenPicker(null); }} style={{ marginTop: 6, width: '100%', fontSize: 11, padding: '3px 0', border: '1px solid var(--ed-border)', borderRadius: 4, cursor: 'pointer', background: 'var(--ed-surface-2)' }}>Clear</button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Device settings */}
      <h3 style={{ ...sectionTitle, marginTop: 14 }}>Device Settings</h3>
      <Field label="Keep screen awake">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={device_settings.keep_awake ?? true}
            onChange={(e) => setDeviceSettings({ keep_awake: e.target.checked })}
          />
          <span style={{ fontSize: 11, color: 'var(--ed-text-2)' }}>On by default (can be toggled on device)</span>
        </label>
      </Field>

      <Field label="Screensaver after">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <select
            value={device_settings.screensaver_timeout ?? 0}
            onChange={(e) => setDeviceSettings({ screensaver_timeout: Number(e.target.value) })}
            style={{ fontSize: 12, padding: '3px 4px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)' }}
          >
            <option value={0}>Off</option>
            <option value={30}>30 sec</option>
            <option value={60}>1 min</option>
            <option value={120}>2 min</option>
            <option value={300}>5 min</option>
            <option value={600}>10 min</option>
          </select>
          <span style={{ fontSize: 11, color: 'var(--ed-text-3)' }}>of inactivity</span>
        </div>
      </Field>

      <Field label="Clock size">
        <select
          value={device_settings.screensaver_font_size ?? 144}
          onChange={(e) => setDeviceSettings({ screensaver_font_size: Number(e.target.value) })}
          style={{ fontSize: 12, padding: '3px 4px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)' }}
        >
          <option value={96}>S (96pt)</option>
          <option value={144}>M (144pt)</option>
          <option value={192}>L (192pt)</option>
          <option value={240}>XL (240pt)</option>
          <option value={288}>XXL (288pt)</option>
        </select>
      </Field>

      <Field label="Banner text">
        <input
          type="text"
          value={banner ?? ''}
          onChange={(e) => setBanner(e.target.value)}
          style={inputStyle}
          placeholder="e.g. Main Panel"
        />
      </Field>

      <Field label="Columns">
        <input
          type="number"
          min={1}
          max={40}
          value={displayGrid.columns}
          onChange={(e) => patchGrid({ columns: num(e.target.value, 1) })}
          style={{ ...inputStyle, width: 64 }}
        />
      </Field>

      <Field label="Cell width (px)">
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <input
            type="number"
            min={1}
            value={displayGrid.widget_dimensions[0]}
            onChange={(e) => patchGrid({ widget_dimensions: [num(e.target.value, 1), displayGrid.widget_dimensions[1]] })}
            style={{ ...inputStyle, width: 70 }}
          />
          <button
            onClick={() => patchGrid({ widget_dimensions: [autoW, displayGrid.widget_dimensions[1]] })}
            title={`Set to ${autoW}pt to fill content width`}
            style={{ fontSize: 10, padding: '3px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-surface)', cursor: 'pointer', whiteSpace: 'nowrap', color: 'var(--ed-text-2)' }}
          >
            ↔ Fill ({autoW})
          </button>
        </div>
      </Field>

      <Field label="Cell height (px)">
        <input
          type="number"
          min={1}
          value={displayGrid.widget_dimensions[1]}
          onChange={(e) => patchGrid({ widget_dimensions: [displayGrid.widget_dimensions[0], num(e.target.value, 1)] })}
          style={{ ...inputStyle, width: 70 }}
        />
      </Field>

      <Field label="Margin X (px)">
        <input
          type="number"
          min={0}
          value={displayGrid.widget_margins[0]}
          onChange={(e) => patchGrid({ widget_margins: [num(e.target.value), displayGrid.widget_margins[1]] })}
          style={{ ...inputStyle, width: 64 }}
        />
      </Field>
      <Field label="Margin Y (px)">
        <input
          type="number"
          min={0}
          value={displayGrid.widget_margins[1]}
          onChange={(e) => patchGrid({ widget_margins: [displayGrid.widget_margins[0], num(e.target.value)] })}
          style={{ ...inputStyle, width: 64 }}
        />
      </Field>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, gap: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--ed-text-2)', flexShrink: 0 }}>{label}</label>
      {children}
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: '0 0 10px', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
const inputStyle = { fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4, background: 'var(--ed-input-bg)', width: '100%' };
