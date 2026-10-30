import { useState } from 'react';
import { useEntityStore } from '../../store/entityStore';
import { EMBEDDED, listEntityIds } from '../../utils/haEmbed';

export default function EntityManager() {
  const { entities, addEntity, removeEntity, bulkAdd, clearAll } = useEntityStore();

  const [singleInput, setSingleInput] = useState('');
  const [bulkInput, setBulkInput] = useState('');
  const [tab, setTab] = useState('list'); // 'list' | 'bulk' | 'sync'
  const [filter, setFilter] = useState('');
  const [syncStatus, setSyncStatus] = useState('');
  const [syncing, setSyncing] = useState(false);

  function handleAdd() {
    addEntity(singleInput);
    setSingleInput('');
  }

  function handleBulkAdd() {
    if (bulkInput.trim()) {
      bulkAdd(bulkInput);
      setBulkInput('');
      setTab('list');
    }
  }

  async function handleSyncFromHA() {
    if (EMBEDDED) {
      setSyncing(true); setSyncStatus('');
      try {
        const ids = await listEntityIds();
        bulkAdd(ids.join('\n'));
        setSyncStatus(`ok:Imported ${ids.length} entities from HA.`);
      } catch (e) {
        setSyncStatus(`error:${e.message || e}`);
      } finally {
        setSyncing(false);
      }
      return;
    }
    setSyncStatus('error:Open the editor from Home Assistant to sync entities.');
  }

  const filtered = filter
    ? entities.filter((e) => e.toLowerCase().includes(filter.toLowerCase()))
    : entities;

  // Group by domain for readability
  const grouped = {};
  filtered.forEach((e) => {
    const domain = e.includes('.') ? e.split('.')[0] : 'other';
    if (!grouped[domain]) grouped[domain] = [];
    grouped[domain].push(e);
  });

  const canSync = EMBEDDED;
  const statusIsError = syncStatus.startsWith('error:');
  const statusMsg = syncStatus.replace(/^(ok|error):/, '');

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <h3 style={sectionTitle}>Entity List</h3>
        <span style={{ fontSize: 11, color: 'var(--ed-text-3)' }}>{entities.length} saved</span>
      </div>

      <p style={{ fontSize: 11, color: 'var(--ed-text-3)', marginBottom: 8, lineHeight: 1.4 }}>
        Entity IDs saved here appear as autocomplete options on all entity fields.
      </p>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 10, borderBottom: '1px solid var(--ed-divider-2)' }}>
        {[['list', 'List'], ['bulk', 'Bulk add'], ['sync', '⟳ Sync from HA']].map(([t, lbl]) => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '4px 10px', fontSize: 12, border: 'none', background: 'none', cursor: 'pointer',
            borderBottom: tab === t ? '2px solid var(--ed-primary)' : '2px solid transparent',
            color: tab === t ? 'var(--ed-primary)' : 'var(--ed-text-2)', fontWeight: tab === t ? 600 : 400,
          }}>{lbl}</button>
        ))}
      </div>

      {tab === 'list' && (
        <>
          {/* Add single */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
            <input
              type="text"
              value={singleInput}
              onChange={(e) => setSingleInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              placeholder="light.bedroom"
              style={{ flex: 1, fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4 }}
            />
            <button onClick={handleAdd} style={btnStyle('var(--ed-primary)')}>+ Add</button>
          </div>

          {/* Filter */}
          {entities.length > 5 && (
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter entities..."
              style={{ width: '100%', fontSize: 11, padding: '3px 6px', border: '1px solid var(--ed-divider-2)', borderRadius: 4, marginBottom: 6, boxSizing: 'border-box' }}
            />
          )}

          {/* Entity list grouped by domain */}
          {entities.length === 0 ? (
            <p style={{ fontSize: 11, color: 'var(--ed-text-3)', textAlign: 'center', padding: '16px 0' }}>
              No entities yet — add one above, use Bulk add, or Sync from HA
            </p>
          ) : (
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              {Object.entries(grouped).sort().map(([domain, ids]) => (
                <div key={domain} style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 10, color: 'var(--ed-text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
                    {domain}
                  </div>
                  {ids.map((id) => (
                    <div key={id} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0' }}>
                      <span style={{ flex: 1, fontSize: 12, color: 'var(--ed-text)', fontFamily: 'monospace' }}>{id}</span>
                      <button
                        onClick={() => removeEntity(id)}
                        style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--ed-text-3)', fontSize: 14, padding: '0 2px', lineHeight: 1 }}
                        title="Remove"
                      >×</button>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {entities.length > 0 && (
            <button
              onClick={() => { if (window.confirm('Clear all entities?')) clearAll(); }}
              style={{ ...btnStyle('var(--ed-error)'), marginTop: 8, fontSize: 11 }}
            >
              Clear all
            </button>
          )}
        </>
      )}

      {tab === 'bulk' && (
        <>
          <p style={{ fontSize: 11, color: 'var(--ed-text-2)', marginBottom: 6 }}>
            Paste entity IDs — one per line, or comma-separated.<br />
            Tip: copy from HA Developer Tools → States.
          </p>
          <textarea
            value={bulkInput}
            onChange={(e) => setBulkInput(e.target.value)}
            placeholder={'light.bedroom\nswitch.kitchen\nsensor.temperature'}
            rows={8}
            style={{ width: '100%', fontSize: 12, padding: 6, border: '1px solid var(--ed-border)', borderRadius: 4, fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box' }}
          />
          <button onClick={handleBulkAdd} style={{ ...btnStyle('var(--ed-primary)'), marginTop: 6 }}>
            Add all
          </button>
        </>
      )}

      {tab === 'sync' && (
        <>
          {EMBEDDED ? (
            <p style={{ fontSize: 11, color: 'var(--ed-text-2)', marginBottom: 10, lineHeight: 1.5 }}>
              Inside Home Assistant the entity list syncs automatically when the editor opens.
              Fetch again after adding new entities.
            </p>
          ) : (
            <>
              <p style={{ fontSize: 11, color: 'var(--ed-text-2)', marginBottom: 10, lineHeight: 1.5 }}>
                Entity sync works in the editor inside Home Assistant (integration options → Open the dashboard editor).
                Here you can add entity IDs by hand or in bulk.
              </p>
            </>
          )}

          <button
            onClick={handleSyncFromHA}
            disabled={syncing || !canSync}
            style={{ ...btnStyle('var(--ed-primary)'), opacity: canSync ? 1 : 0.5, cursor: canSync ? 'pointer' : 'not-allowed' }}
          >
            {syncing ? 'Fetching…' : '⟳ Fetch entity list from HA'}
          </button>

          {statusMsg && (
            <div style={{
              marginTop: 10, padding: '6px 10px', borderRadius: 4, fontSize: 11,
              background: statusIsError ? 'var(--ed-err-bg)' : 'var(--ed-ok-bg)',
              border: `1px solid ${statusIsError ? 'var(--ed-err-border)' : 'var(--ed-ok-border)'}`,
              color: statusIsError ? 'var(--ed-error)' : 'var(--ed-success)',
            }}>
              {statusMsg}
            </div>
          )}
        </>
      )}
    </div>
  );
}

const sectionTitle = { fontSize: 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', color: 'var(--ed-section-color)', margin: 0, textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' };
function btnStyle(bg) {
  return { padding: '4px 10px', fontSize: 12, fontWeight: 500, border: 'none', borderRadius: 4, background: bg, color: bg === 'var(--ed-primary)' ? 'var(--ed-on-primary)' : '#fff', cursor: 'pointer' };
}
