import { useEffect, useRef, useState } from 'react';
import {
  mdiTrayArrowDown, mdiUndo, mdiRedo, mdiDotsVertical, mdiCodeJson, mdiHelpCircleOutline,
  mdiDeleteOutline, mdiCropPortrait, mdiCropLandscape, mdiTune, mdiCheck, mdiAlertCircleOutline, mdiSend,
} from '@mdi/js';
import { useEditorStore } from '../store/editorStore';
import { useHaStore } from '../store/haStore';
import { buildProfile } from '../utils/profileExport';
import { listDevices, getProfile, applyProfile, loadProfileIntoEditor, useHostNarrow } from '../utils/haEmbed';
import { deviceForScreen } from '../data/deviceModels';
import { Icon, IconButton, Segmented } from './ui';

export default function Header({ onProfile, onHelp, layout = {}, configToggle = null }) {
  const editor = useEditorStore();
  const { orientation, setOrientation, setDevice, undo, redo, history, future, reset } = editor;
  const dirty = useEditorStore((s) => s.isDirty());
  const ha = useHaStore();
  const [devices, setDevices] = useState([]);
  const [status, setStatus] = useState({ kind: 'idle', text: '' }); // idle | busy | ok | err
  const hostNarrow = useHostNarrow(); // HA sidebar hidden → its menu button sits in our top-left corner
  const timer = useRef(null);

  function flash(kind, text, ms = 3000) {
    clearTimeout(timer.current);
    setStatus({ kind, text });
    if (ms) timer.current = setTimeout(() => setStatus({ kind: 'idle', text: '' }), ms);
  }

  // Canvas follows the panel: its screen, and the orientation it runs in
  function adoptPanel(dev) {
    if (!dev) return;
    setDevice(deviceForScreen(dev.screen));
    if (dev.orientation === 'portrait' || dev.orientation === 'landscape') setOrientation(dev.orientation);
  }

  async function load(dev, { quiet = false } = {}) {
    flash('busy', 'Loading…', 0);
    try {
      const profile = await getProfile(dev.device_id);
      if (!loadProfileIntoEditor(profile, dev.orientation)) throw new Error(`${dev.device_id} has no layout yet`);
      flash('ok', quiet ? '' : `Loaded ${dev.device_id}`);
    } catch (err) {
      flash('err', err.message || String(err), 5000);
    }
  }

  useEffect(() => {
    listDevices().then((list) => {
      setDevices(list);
      const wanted = new URLSearchParams(window.location.search).get('device');
      const ids = list.map((d) => d.device_id);
      const pick = (wanted && ids.includes(wanted)) ? wanted : (ids.includes(ha.deviceId) ? ha.deviceId : ids[0]);
      if (pick && pick !== ha.deviceId) ha.setDeviceId(pick);
      const dev = list.find((d) => d.device_id === pick);
      adoptPanel(dev);
      // Nothing designed yet: start from what the panel is showing right now
      const empty = !useEditorStore.getState().pages?.some((p) => p.widgets?.length);
      if (dev && empty && dev.has_profile) load(dev, { quiet: true });
    }).catch((err) => flash('err', err.message || String(err), 0));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const current = devices.find((d) => d.device_id === ha.deviceId);

  function pickPanel(id) {
    ha.setDeviceId(id);
    adoptPanel(devices.find((d) => d.device_id === id));
  }

  function handleLoad() {
    if (!current) return;
    if (dirty && !window.confirm(`Replace the canvas with the layout ${current.device_id} is showing? Unsaved changes are lost.`)) return;
    load(current);
  }

  async function handleDeploy() {
    if (!current) return;
    flash('busy', 'Deploying…', 0);
    try {
      await applyProfile(current.device_id, buildProfile(useEditorStore.getState()));
      useEditorStore.getState().markSaved();
      setDevices((list) => list.map((d) => (d.device_id === current.device_id ? { ...d, has_profile: true } : d)));
      flash('ok', `Deployed to ${current.device_id}`);
    } catch (err) {
      flash('err', err.message || String(err), 6000);
    }
  }

  const busy = status.kind === 'busy';
  const { tight } = layout;

  return (
    <header style={{
      height: 56, display: 'flex', alignItems: 'center', gap: 8,
      padding: hostNarrow ? '0 12px 0 60px' : '0 12px',
      background: 'var(--ed-surface)', borderBottom: '1px solid var(--ed-divider)', color: 'var(--ed-text)',
      whiteSpace: 'nowrap', flexShrink: 0, position: 'relative', zIndex: 100,
    }}>
      <select className="ed-select" value={ha.deviceId} onChange={(e) => pickPanel(e.target.value)}
        title="Panel to design for" style={{ flex: '0 1 auto', maxWidth: tight ? 150 : 240 }}>
        {devices.length === 0 && <option value="">No panels yet</option>}
        {devices.map((d) => (
          <option key={d.device_id} value={d.device_id}>
            {d.device_id}{d.battery != null ? ` · ${d.battery}%` : ''}{d.has_profile ? '' : ' · no layout'}
          </option>
        ))}
      </select>
      <button type="button" className="ed-btn ed-btn--outlined" onClick={handleLoad} disabled={!current?.has_profile || busy}
        title="Replace the canvas with the layout this panel is showing" style={tight ? { padding: '0 10px' } : undefined}>
        <Icon path={mdiTrayArrowDown} size={18} />{!tight && 'Load'}
      </button>

      <span className="ed-vsep" style={{ margin: '0 4px' }} />

      <Segmented ariaLabel="Orientation" value={orientation} onChange={setOrientation} options={[
        { value: 'portrait', icon: mdiCropPortrait, title: 'Portrait' },
        { value: 'landscape', icon: mdiCropLandscape, title: 'Landscape' },
      ]} />
      <IconButton path={mdiUndo} title="Undo (Ctrl+Z)" onClick={undo} disabled={!history?.length} />
      <IconButton path={mdiRedo} title="Redo (Ctrl+Shift+Z)" onClick={redo} disabled={!future?.length} />

      <span title={status.text} style={{
        flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 13, paddingLeft: 4,
        color: status.kind === 'err' ? 'var(--ed-error)' : 'var(--ed-text-2)',
      }}>
        {!tight && status.text}
      </span>

      <MoreMenu items={[
        { icon: mdiCodeJson, label: 'Profile JSON…', onClick: onProfile },
        { icon: mdiHelpCircleOutline, label: 'Help', onClick: onHelp },
        'sep',
        { icon: mdiDeleteOutline, label: 'Clear layout', confirm: 'Click again to clear', danger: true, onClick: reset },
      ]} />
      <button type="button" className={`ed-btn ed-btn--filled ${status.kind === 'ok' ? 'ed-btn--ok' : status.kind === 'err' ? 'ed-btn--err' : ''}`}
        onClick={handleDeploy} disabled={busy || !current}
        title={current ? `Send this layout to ${current.device_id}${dirty ? ' (unsaved changes)' : ''}` : 'No panel selected'}>
        <Icon path={status.kind === 'ok' ? mdiCheck : status.kind === 'err' ? mdiAlertCircleOutline : mdiSend} size={18} />
        Deploy
        {dirty && status.kind === 'idle' && <span className="ed-dirty-dot" title="Unsaved changes" />}
      </button>
      {configToggle && (
        <IconButton path={mdiTune} pressed={configToggle.open} onClick={configToggle.onToggle}
          title={configToggle.open ? 'Hide settings' : 'Show settings'} />
      )}
    </header>
  );
}

/** Secondary actions. Items: { icon, label, onClick, confirm?, danger? } or 'sep'. */
function MoreMenu({ items }) {
  const [open, setOpen] = useState(false);
  const [armed, setArmed] = useState(null);
  const ref = useRef(null);

  function close() { setOpen(false); setArmed(null); }

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (!ref.current?.contains(e.target)) close(); };
    const onKey = (e) => { if (e.key === 'Escape') close(); };
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
      <IconButton path={mdiDotsVertical} title="More" pressed={open} aria-haspopup="menu" onClick={() => (open ? close() : setOpen(true))} />
      {open && (
        <div className="ed-menu" role="menu">
          {items.map((it, i) => (it === 'sep' ? <div key={`sep${i}`} className="ed-menu-sep" /> : (
            <button key={it.label} type="button" role="menuitem"
              className={`ed-menu-item ${it.danger && armed === it.label ? 'ed-menu-item--danger' : ''}`} onClick={() => pick(it)}>
              <Icon path={it.icon} size={20} />
              <span>{armed === it.label ? it.confirm : it.label}</span>
            </button>
          )))}
        </div>
      )}
    </div>
  );
}
