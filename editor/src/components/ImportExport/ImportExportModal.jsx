import { useState, useRef } from 'react';
import { useEditorStore } from '../../store/editorStore';
import { buildProfile, parseProfile, profileToState } from '../../utils/profileExport';
import { EMBEDDED } from '../../utils/haEmbed';

/** Collect every unique entity_id from all pages. */
function collectEntityIds(pages) {
  const ids = new Set();
  const ENTITY_KEYS = ['entity_id', 'nozzle_entity', 'bed_entity', 'time_entity', 'progress_entity', 'status_entity'];
  for (const page of (pages ?? [])) {
    for (const w of (page.widgets ?? [])) {
      for (const k of ENTITY_KEYS) { if (w[k]) ids.add(w[k]); }
      if (w.overlay_button?.entity_id) ids.add(w.overlay_button.entity_id);
    }
  }
  return [...ids].sort();
}

export default function ImportExportModal({ mode, onClose }) {
  const state = useEditorStore();
  const { pages, setPages, setGridConfig, setBanner, setNavbarEdge, setNavbarStyle, setNavbarShowBattery, setNavbarShowKeepAwake, setDeviceSettings } = useEditorStore();

  const [tab, setTab] = useState('paste');
  const [pasteValue, setPasteValue] = useState('');
  const [parseError, setParseError] = useState('');
  const [copyDone, setCopyDone] = useState(false);
  const [shareDone, setShareDone] = useState(false);
  const [mirrorCopied, setMirrorCopied] = useState(false);
  const fileInputRef = useRef(null);

  const profileJson = mode === 'export' ? JSON.stringify(buildProfile(state), null, 2) : '';
  const mirrorEntities = mode === 'export' ? collectEntityIds(pages) : [];

  function handleCopy() {
    navigator.clipboard.writeText(profileJson).then(() => {
      setCopyDone(true);
      setTimeout(() => setCopyDone(false), 2000);
    });
  }

  function handleShareLink() {
    // URL-safe base64: replace +/= chars that break URLs in email/Slack/etc.
    const b64 = btoa(encodeURIComponent(profileJson))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    const url = `${window.location.origin}${window.location.pathname}#profile=${b64}`;
    navigator.clipboard.writeText(url).then(() => {
      setShareDone(true);
      setTimeout(() => setShareDone(false), 3000);
    });
  }

  function handleDownload() {
    const blob = new Blob([profileJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mqtt_dash_profile.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleCopyMirrorList() {
    navigator.clipboard.writeText(mirrorEntities.join('\n')).then(() => {
      setMirrorCopied(true);
      setTimeout(() => setMirrorCopied(false), 2000);
    });
  }

  function doImport(jsonStr) {
    const result = parseProfile(jsonStr);
    if (!result.ok) { setParseError(result.error); return; }
    const s = profileToState(result.data);
    setGridConfig(s.grid);
    setPages(s.pages);
    setBanner(s.banner ?? '');
    if (s.navbar_edge) setNavbarEdge(s.navbar_edge);
    if (s.navbar_style) setNavbarStyle(s.navbar_style);
    setNavbarShowBattery(s.navbar_show_battery !== false);
    setNavbarShowKeepAwake(s.navbar_show_keepawake !== false);
    if (s.device_settings) setDeviceSettings(s.device_settings);
    setParseError('');
    onClose();
  }

  function handleFileImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => doImport(ev.target.result);
    reader.readAsText(file);
  }

  return (
    <div style={overlayStyle} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={modalStyle}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>
            {mode === 'export' ? '⬇ Export Profile' : '⬆ Import Profile'}
          </h2>
          <button onClick={onClose} style={{ border: 'none', background: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--ed-text-2)' }}>×</button>
        </div>

        {mode === 'export' && (
          <>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <button onClick={handleCopy} style={actionBtn(copyDone ? '#4caf50' : 'var(--ed-primary)', true)}>
                {copyDone ? '✓ Copied!' : '📋 Copy JSON'}
              </button>
              <button onClick={handleDownload} style={actionBtn('#37474f')}>
                ⬇ Download .json
              </button>
              <button onClick={handleShareLink} style={actionBtn(shareDone ? '#4caf50' : '#0277bd')}>
                {shareDone ? '✓ Link copied!' : '🔗 Share link'}
              </button>
            </div>

            <pre style={{
              background: '#1e1e2e', color: '#cdd6f4', padding: 12, borderRadius: 6,
              fontSize: 11, overflow: 'auto', maxHeight: 300, margin: 0, fontFamily: 'monospace',
            }}>
              {profileJson}
            </pre>

            {/* Mirror checklist */}
            {mirrorEntities.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <h3 style={{ fontSize: 13, fontWeight: 600, margin: 0, color: 'var(--ed-text)' }}>
                    HA Mirror entities ({mirrorEntities.length})
                  </h3>
                  <button onClick={handleCopyMirrorList} style={actionBtn(mirrorCopied ? '#4caf50' : '#546e7a')}>
                    {mirrorCopied ? '✓ Copied' : '📋 Copy list'}
                  </button>
                </div>
                <p style={{ fontSize: 11, color: 'var(--ed-text-3)', margin: '0 0 8px' }}>
                  These entities are used in the profile. Configure them as mirrored entities in the HA integration.
                  Not included in the exported JSON.
                </p>
                <div style={{ background: 'var(--ed-surface-2)', borderRadius: 6, border: '1px solid var(--ed-divider)', padding: '8px 10px' }}>
                  {mirrorEntities.map((id) => {
                    const domain = id.split('.')[0];
                    return (
                      <div key={id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderBottom: '1px solid var(--ed-divider-2)' }}>
                        <span style={{ fontSize: 10, color: '#fff', background: domainColor(domain), borderRadius: 3, padding: '1px 5px', fontWeight: 600, flexShrink: 0 }}>
                          {domain}
                        </span>
                        <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--ed-text)' }}>{id}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Send to Home Assistant */}
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--ed-divider)' }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px', color: 'var(--ed-text)' }}>
                Send to Home Assistant
              </h3>

              <p style={{ fontSize: 12, color: 'var(--ed-text-2)', margin: '4px 0 0' }}>
                {EMBEDDED
                  ? <>Pick the panel in the toolbar and press <strong>⚡ Deploy</strong>.</>
                  : <>Deploy from the editor inside Home Assistant: Settings → Devices &amp; services → iPad MQTT Dashboard → Configure → <strong>Open the dashboard editor</strong>. Here you can only copy or download the JSON.</>}
              </p>
            </div>
          </>
        )}

        {mode === 'import' && (
          <>
            <div style={{ display: 'flex', gap: 0, marginBottom: 12, borderBottom: '1px solid var(--ed-divider)' }}>
              {[['paste', '📋 Paste JSON'], ['file', '📁 Load file']].map(([t, lbl]) => (
                <button key={t} onClick={() => setTab(t)} style={{
                  padding: '6px 16px', fontSize: 13, border: 'none', background: 'none', cursor: 'pointer',
                  borderBottom: tab === t ? '2px solid var(--ed-primary)' : '2px solid transparent',
                  color: tab === t ? 'var(--ed-primary)' : 'var(--ed-text-2)', fontWeight: tab === t ? 600 : 400,
                }}>{lbl}</button>
              ))}
            </div>

            {tab === 'paste' && (
              <>
                <textarea
                  value={pasteValue}
                  onChange={(e) => setPasteValue(e.target.value)}
                  placeholder="Paste profile JSON here..."
                  rows={10}
                  style={{ width: '100%', boxSizing: 'border-box', fontSize: 12, padding: 8, border: '1px solid var(--ed-border)', borderRadius: 4, fontFamily: 'monospace', resize: 'vertical' }}
                />
                <button onClick={() => doImport(pasteValue)} style={{ ...actionBtn('var(--ed-primary)', true), marginTop: 8 }}>
                  Import
                </button>
              </>
            )}

            {tab === 'file' && (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <input ref={fileInputRef} type="file" accept=".json" onChange={handleFileImport} style={{ display: 'none' }} />
                <button onClick={() => fileInputRef.current?.click()} style={actionBtn('#37474f')}>
                  📁 Choose JSON file
                </button>
              </div>
            )}

            {parseError && (
              <p style={{ color: 'var(--ed-error)', fontSize: 12, marginTop: 8, background: 'var(--ed-err-bg)', padding: '6px 8px', borderRadius: 4 }}>
                Error: {parseError}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const DOMAIN_COLORS = { light: '#f59e0b', switch: '#3b82f6', sensor: '#10b981', climate: '#ef4444', camera: '#8b5cf6', scene: '#ec4899', button: '#6366f1', person: '#14b8a6', weather: '#0ea5e9', printer: '#f97316' };
function domainColor(domain) {
  return DOMAIN_COLORS[domain] ?? '#94a3b8';
}

const overlayStyle = {
  position: 'fixed', inset: 0, background: 'var(--ed-overlay)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
};
const modalStyle = {
  background: 'var(--ed-surface)', color: 'var(--ed-text)',
  border: EMBEDDED ? '1px solid var(--ed-divider)' : 'none',
  borderRadius: EMBEDDED ? 'var(--ed-radius)' : 10, padding: 24, width: 580,
  maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto',
  boxShadow: 'var(--ed-shadow)',
};
// Standalone keeps its colour-coded buttons; inside HA secondary actions are tonal
function actionBtn(color, primary = false) {
  const tonal = EMBEDDED && !primary;
  return {
    padding: '7px 14px', fontSize: 13, fontWeight: 500, borderRadius: 'var(--ed-btn-radius)', border: 'none', cursor: 'pointer',
    background: tonal ? 'var(--ed-neutral)' : color,
    color: tonal ? 'var(--ed-on-neutral)' : primary ? 'var(--ed-on-primary)' : '#fff',
  };
}
