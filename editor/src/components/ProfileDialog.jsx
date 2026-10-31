// The layout as profile JSON: copy or download it as a backup, or paste / open
// a file and load it into the editor (Deploy then sends it to the panel).
import { useMemo, useRef, useState } from 'react';
import { mdiContentCopy, mdiDownload, mdiFolderOpenOutline, mdiCheck } from '@mdi/js';
import { useEditorStore } from '../store/editorStore';
import { useHaStore } from '../store/haStore';
import { buildProfile, parseProfile } from '../utils/profileExport';
import { loadProfileIntoEditor } from '../utils/haEmbed';
import { Dialog, Icon } from './ui';

export default function ProfileDialog({ onClose }) {
  const state = useEditorStore();
  const deviceId = useHaStore((s) => s.deviceId);
  const current = useMemo(() => JSON.stringify(buildProfile(state), null, 2), [state]);
  const [text, setText] = useState(current);
  const [msg, setMsg] = useState(null); // { ok, text }
  const fileRef = useRef(null);
  const edited = text !== current;

  async function copy() {
    try { await navigator.clipboard.writeText(text); setMsg({ ok: true, text: 'Copied' }); } catch { setMsg({ ok: false, text: 'The browser blocked the clipboard; select the text and copy it instead' }); }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `${deviceId || 'panel'}-layout.json` });
    a.click();
    URL.revokeObjectURL(url);
  }

  function openFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((t) => { setText(t); setMsg(null); });
    e.target.value = '';
  }

  function load() {
    const parsed = parseProfile(text);
    if (!parsed.ok) { setMsg({ ok: false, text: `Not a layout: ${parsed.error}` }); return; }
    if (!loadProfileIntoEditor(parsed.data, undefined, { saved: false })) { setMsg({ ok: false, text: 'Not a layout this editor can read' }); return; }
    onClose();
  }

  return (
    <Dialog title="Profile JSON" onClose={onClose} width={680} actions={(
      <>
        <button type="button" className="ed-btn" onClick={copy}><Icon path={msg?.text === 'Copied' ? mdiCheck : mdiContentCopy} size={18} />Copy</button>
        <button type="button" className="ed-btn" onClick={download}><Icon path={mdiDownload} size={18} />Download</button>
        <button type="button" className="ed-btn" onClick={() => fileRef.current?.click()}><Icon path={mdiFolderOpenOutline} size={18} />Open file</button>
        <input ref={fileRef} type="file" accept=".json,application/json" hidden onChange={openFile} />
        <span className="ed-spacer" />
        <button type="button" className="ed-btn ed-btn--filled" disabled={!edited} onClick={load}
          title={edited ? 'Replace the canvas with this JSON' : 'Paste or open a layout first'}>Load into editor</button>
      </>
    )}>
      <p className="ed-hint">The layout as the panel receives it. Paste or open a saved one and load it, then Deploy to send it to the panel.</p>
      <textarea className="ed-input ed-input--mono" spellCheck={false} value={text} rows={18}
        onChange={(e) => { setText(e.target.value); setMsg(null); }} style={{ width: '100%', fontSize: 12 }} aria-label="Profile JSON" />
      {msg && <div className={`ed-msg ${msg.ok ? 'ed-msg--ok' : 'ed-msg--err'}`} style={{ marginTop: 8 }}>{msg.text}</div>}
    </Dialog>
  );
}
