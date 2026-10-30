import { useEffect, useRef, useState } from 'react';
import { useEditorStore } from '../store/editorStore';
import { useHaStore } from '../store/haStore';
import { buildProfile } from '../utils/profileExport';
import { EMBEDDED, listDevices, getProfile, applyProfile, loadProfileIntoEditor, useHostNarrow } from '../utils/haEmbed';
import DeviceSelector from './DeviceSelector';

export default function Header({ onImport, onExport, onHelp, layout = {}, configToggle = null }) {
  const { pages, device, reset, undo, redo, history, future } = useEditorStore();
  const editorState = useEditorStore();
  const ha = useHaStore();
  const widgetCount = pages?.reduce((n, p) => n + (p.widgets?.length ?? 0), 0) ?? 0;
  const [showReset, setShowReset] = useState(false);
  const [deployState, setDeployState] = useState('idle'); // idle | sending | ok | err
  const [deployMsg, setDeployMsg] = useState('');
  const [devices, setDevices] = useState([]);
  const hostNarrow = useHostNarrow(); // HA sidebar hidden → its ☰ button sits in our top-left corner

  // Embedded in HA: the panels come straight from the integration
  useEffect(() => {
    if (!EMBEDDED) return;
    listDevices().then((list) => {
      setDevices(list);
      const wanted = new URLSearchParams(window.location.search).get('device');
      const ids = list.map((d) => d.device_id);
      const pick = (wanted && ids.includes(wanted)) ? wanted : (ids.includes(ha.deviceId) ? ha.deviceId : ids[0]);
      if (pick && pick !== ha.deviceId) ha.setDeviceId(pick);
      // Empty editor: start from what the panel is showing right now
      const empty = !useEditorStore.getState().pages?.some((p) => p.widgets?.length);
      if (pick && empty && list.find((d) => d.device_id === pick)?.has_profile) {
        const orient = list.find((d) => d.device_id === pick)?.orientation;
        getProfile(pick).then((prof) => {
          if (loadProfileIntoEditor(prof, orient)) { setDeployState('ok'); setDeployMsg(`Loaded "${pick}"`); setTimeout(() => setDeployState('idle'), 2500); }
        }).catch(() => {});
      }
    }).catch((err) => { setDeployState('err'); setDeployMsg(err.message); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLoadFromHA() {
    if (!ha.deviceId) return;
    if ((pages?.some((p) => p.widgets?.length)) && !window.confirm(`Replace the current layout with "${ha.deviceId}"'s saved profile?`)) return;
    setDeployState('sending');
    try {
      const profile = await getProfile(ha.deviceId);
      const orient = devices.find((d) => d.device_id === ha.deviceId)?.orientation;
      if (!loadProfileIntoEditor(profile, orient)) throw new Error(`"${ha.deviceId}" has no saved profile yet`);
      setDeployState('ok'); setDeployMsg(`Loaded "${ha.deviceId}"`);
      setTimeout(() => setDeployState('idle'), 2000);
    } catch (err) {
      setDeployState('err'); setDeployMsg(err.message);
      setTimeout(() => setDeployState('idle'), 5000);
    }
  }

  function handleReset() {
    if (showReset) { reset(); setShowReset(false); }
    else setShowReset(true);
  }

  // Deploying only exists inside Home Assistant (the integration's editor panel)
  async function handleDeploy() {
    if (EMBEDDED) {
      if (!ha.deviceId) return;
      setDeployState('sending'); setDeployMsg('');
      try {
        await applyProfile(ha.deviceId, buildProfile(editorState));
        setDeployState('ok'); setDeployMsg(`Deployed to "${ha.deviceId}"`);
        setTimeout(() => setDeployState('idle'), 3000);
      } catch (err) {
        setDeployState('err'); setDeployMsg(err.message || String(err));
        setTimeout(() => setDeployState('idle'), 5000);
      }
      return;
    }
  }

  const deployLabel = deployState === 'sending' ? '…'
    : deployState === 'ok' ? '✓ Sent'
    : deployState === 'err' ? '✗ Error'
    : '⚡ Deploy';
  const deployTitle = deployState === 'err' ? deployMsg
    : `Deploy to ${ha.deviceId || '(no panel)'}`;

  const statusColor = deployState === 'err' ? 'var(--ed-error)' : 'var(--ed-success)';
  const showStatus = deployState !== 'idle' && !!deployMsg;

  if (EMBEDDED) {
    // HA-native toolbar: one row that never wraps.
    // left = HA panel (source/target) · middle = canvas · right = actions
    const deployVariant = deployState === 'ok' ? 'ed-btn--ok' : deployState === 'err' ? 'ed-btn--err' : '';
    const { toolbarMenu, tight } = layout;
    return (
      <header style={{
        height: 52,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: hostNarrow ? '0 12px 0 60px' : '0 12px',
        background: 'var(--ed-surface)',
        borderBottom: '1px solid var(--ed-divider)',
        color: 'var(--ed-text)',
        whiteSpace: 'nowrap',
        flexShrink: 0,
        position: 'relative',
        zIndex: 100,
      }}>
        <select
          className="ed-select"
          value={ha.deviceId}
          onChange={(e) => ha.setDeviceId(e.target.value)}
          title="Panel to load from / deploy to"
          style={{ flex: '0 1 auto', maxWidth: tight ? 150 : 220 }}
        >
          {devices.length === 0 && <option value="">No panels</option>}
          {devices.map((d) => (
            <option key={d.device_id} value={d.device_id}>
              {d.device_id}{d.battery != null ? ` · ${d.battery}%` : ''}{d.has_profile ? '' : ' (no profile)'}
            </option>
          ))}
        </select>
        <button
          className="ed-btn ed-btn--outlined"
          onClick={handleLoadFromHA}
          disabled={!ha.deviceId}
          title="Load this panel's saved profile"
          style={tight ? { padding: '0 10px' } : undefined}
        >⤓{!tight && ' Load'}</button>

        <span className="ed-vsep" style={{ marginLeft: 4 }} />

        <DeviceSelector compact />
        <button className="ed-btn ed-icon-btn" onClick={undo} disabled={!history?.length} title="Undo (Ctrl+Z)">↶</button>
        <button className="ed-btn ed-icon-btn" onClick={redo} disabled={!future?.length} title="Redo (Ctrl+Y)">↷</button>

        <span
          title={showStatus ? deployMsg : undefined}
          style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 13, color: 'var(--ed-text-2)' }}
        >
          {!tight && <>{widgetCount} widget{widgetCount !== 1 ? 's' : ''}</>}
          {showStatus && <span style={{ color: statusColor }}>{!tight && ' · '}{deployMsg}</span>}
        </span>

        {!toolbarMenu && (
          <>
            <button className="ed-btn" onClick={onImport} title="Import a profile JSON">⬆ Import</button>
            <button className="ed-btn" onClick={onExport} title="Export / share the profile JSON">⬇ Export</button>
          </>
        )}
        <button
          className={`ed-btn ed-btn--filled ${deployVariant}`}
          onClick={handleDeploy}
          disabled={deployState === 'sending' || !ha.deviceId}
          title={deployTitle}
        >
          {deployLabel}
        </button>
        {toolbarMenu ? (
          <OverflowMenu
            items={[
              { icon: '⬆', label: 'Import', onClick: onImport },
              { icon: '⬇', label: 'Export', onClick: onExport },
              { icon: '?', label: 'Help', onClick: onHelp },
              { icon: '✕', label: 'New (reset all)', confirm: '⚠ Click again to reset', danger: true, onClick: reset },
            ]}
          />
        ) : (
          <>
            <button className="ed-btn ed-icon-btn" onClick={onHelp} title="Help / Tutorial" style={{ fontSize: 15, fontWeight: 600 }}>?</button>
            <button
              className={`ed-btn ${showReset ? 'ed-btn--danger' : ''}`}
              onClick={handleReset}
              onBlur={() => setShowReset(false)}
              title={showReset ? 'Click again to confirm reset' : 'New (reset all)'}
            >
              {showReset ? '⚠ Confirm reset' : '✕ New'}
            </button>
          </>
        )}
        {configToggle && (
          <button
            className="ed-btn ed-icon-btn"
            aria-pressed={configToggle.open}
            onClick={configToggle.onToggle}
            title={configToggle.open ? 'Hide settings panel' : 'Show settings panel'}
          >⚙{'\uFE0E'}</button>
        )}
      </header>
    );
  }

  return (
    <header style={{
      height: 48,
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      background: 'var(--ed-primary)',
      color: 'var(--ed-on-primary)',
      gap: 12,
      flexShrink: 0,
      zIndex: 100,
      whiteSpace: 'nowrap',
    }}>
      {!layout.tight && (
        <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em', marginRight: 8 }}>
          MQTTDash editor (local preview)
        </span>
      )}

      <span style={{ fontSize: 12, color: '#90caf9', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {widgetCount} widget{widgetCount !== 1 ? 's' : ''}
        {device && <> · {device.name}</>}
        {showStatus && (
          <span style={{ marginLeft: 10, color: deployState === 'err' ? '#ef9a9a' : '#a5d6a7' }}>· {deployMsg}</span>
        )}
      </span>

      {/* Undo/Redo */}
      <button
        onClick={undo}
        disabled={history?.length === 0}
        title="Undo (Ctrl+Z)"
        style={btnStyle(history?.length > 0)}
      >↩ Undo</button>
      <button
        onClick={redo}
        disabled={future?.length === 0}
        title="Redo (Ctrl+Y)"
        style={btnStyle(future?.length > 0)}
      >↪ Redo</button>

      <div style={sep} />

      <button onClick={onImport} style={btnStyle(true)}>⬆ Import</button>
      <button onClick={onExport} style={btnStyle(true, '#4caf50')}>⬇ Export</button>

      <div style={sep} />

      <button onClick={onHelp} title="Help / Tutorial" style={btnStyle(true, '#5c6bc0')}>? Help</button>

      <div style={sep} />

      <button
        onClick={handleReset}
        onBlur={() => setShowReset(false)}
        style={btnStyle(true, showReset ? '#ef5350' : undefined)}
        title={showReset ? 'Click again to confirm reset' : 'New (reset all)'}
      >
        {showReset ? '⚠ Confirm Reset' : '✕ New'}
      </button>

      {configToggle && (
        <button
          onClick={configToggle.onToggle}
          title={configToggle.open ? 'Hide config panel' : 'Show config panel'}
          style={btnStyle(true, configToggle.open ? '#5c6bc0' : undefined)}
        >⚙{'\uFE0E'} Config</button>
      )}
    </header>
  );
}

/** "⋯" menu holding the secondary toolbar actions on narrow layouts. */
function OverflowMenu({ items }) {
  const [open, setOpen] = useState(false);
  const [armed, setArmed] = useState(null); // label of an item awaiting confirmation
  const ref = useRef(null);

  function close() { setOpen(false); setArmed(null); }

  useEffect(() => {
    if (!open) return;
    const dismiss = () => { setOpen(false); setArmed(null); };
    function onDown(e) { if (!ref.current?.contains(e.target)) dismiss(); }
    function onKey(e) { if (e.key === 'Escape') dismiss(); }
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  function pick(item) {
    if (item.confirm && armed !== item.label) { setArmed(item.label); return; }
    close();
    item.onClick();
  }

  return (
    <div ref={ref} style={{ position: 'relative', flexShrink: 0 }}>
      <button className="ed-btn ed-icon-btn" aria-pressed={open} aria-haspopup="menu" onClick={() => (open ? close() : setOpen(true))} title="More actions">⋯</button>
      {open && (
        <div className="ed-menu" role="menu">
          {items.map((it) => (
            <button
              key={it.label}
              role="menuitem"
              className={`ed-menu-item ${it.danger && armed === it.label ? 'ed-menu-item--danger' : ''}`}
              onClick={() => pick(it)}
            >
              <span>{it.icon}</span>
              <span>{armed === it.label ? it.confirm : it.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const sep = { width: 1, height: 24, background: '#3949ab', flexShrink: 0 };

function btnStyle(enabled, accent) {
  return {
    padding: '4px 10px',
    fontSize: 12,
    fontWeight: 500,
    borderRadius: 4,
    border: 'none',
    background: accent ? accent : enabled ? '#3949ab' : '#283593',
    color: enabled ? 'var(--ed-on-primary)' : '#7986cb',
    cursor: enabled ? 'pointer' : 'default',
    opacity: enabled ? 1 : 0.5,
    transition: 'background 0.15s',
    flexShrink: 0,
  };
}
