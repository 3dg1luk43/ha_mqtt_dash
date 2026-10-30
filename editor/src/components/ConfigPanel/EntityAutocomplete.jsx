import { useState, useRef, useEffect } from 'react';
import { useEntityStore } from '../../store/entityStore';

/**
 * Smart entity-ID input with a styled dropdown.
 *
 * Features:
 * - Filters stored entity IDs by domain prefix or substring
 * - Groups suggestions by domain
 * - Highlights the matching portion
 * - Keyboard navigation (↑ ↓ Enter Escape)
 * - Falls back to free-text input if no matches
 */
export default function EntityAutocomplete({ value, onChange, placeholder, style }) {
  const { entities } = useEntityStore();
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(-1);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const q = (value || '').trim().toLowerCase();

  // Filter and group matching entities
  const filtered = q.length === 0 ? entities : entities.filter((e) => e.toLowerCase().includes(q));

  const grouped = {};
  filtered.forEach((e) => {
    const domain = e.includes('.') ? e.split('.')[0] : 'other';
    if (!grouped[domain]) grouped[domain] = [];
    grouped[domain].push(e);
  });

  const flat = Object.entries(grouped).sort().flatMap(([, ids]) => ids);
  const hasItems = flat.length > 0;

  function select(id) {
    onChange(id);
    setOpen(false);
    setCursor(-1);
  }

  function handleKeyDown(e) {
    if (!open) {
      if (e.key === 'ArrowDown') { setOpen(true); setCursor(0); e.preventDefault(); }
      return;
    }
    if (e.key === 'ArrowDown') {
      setCursor((c) => Math.min(c + 1, flat.length - 1));
      e.preventDefault();
    } else if (e.key === 'ArrowUp') {
      setCursor((c) => Math.max(c - 1, 0));
      e.preventDefault();
    } else if (e.key === 'Enter' && cursor >= 0 && flat[cursor]) {
      select(flat[cursor]);
      e.preventDefault();
    } else if (e.key === 'Escape') {
      setOpen(false);
      setCursor(-1);
    }
  }

  // Scroll active item into view
  useEffect(() => {
    if (cursor >= 0 && listRef.current) {
      const el = listRef.current.querySelector(`[data-idx="${cursor}"]`);
      if (el) el.scrollIntoView({ block: 'nearest' });
    }
  }, [cursor]);

  function highlight(text, q) {
    if (!q) return text;
    const idx = text.toLowerCase().indexOf(q);
    if (idx < 0) return text;
    return (
      <>
        {text.slice(0, idx)}
        <strong style={{ color: 'var(--ed-primary)' }}>{text.slice(idx, idx + q.length)}</strong>
        {text.slice(idx + q.length)}
      </>
    );
  }

  // Build flat list with group headers interleaved
  const rows = [];
  let flatIdx = 0;
  Object.entries(grouped).sort().forEach(([domain, ids]) => {
    rows.push({ type: 'header', domain });
    ids.forEach((id) => {
      rows.push({ type: 'item', id, idx: flatIdx });
      flatIdx++;
    });
  });

  return (
    <div style={{ position: 'relative', ...style }}>
      <input
        ref={inputRef}
        type="text"
        value={value ?? ''}
        onChange={(e) => { onChange(e.target.value); setOpen(true); setCursor(-1); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder ?? 'e.g. light.bedroom'}
        style={inputStyle}
      />
      {open && hasItems && (
        <div
          ref={listRef}
          style={{
            position: 'absolute', zIndex: 300, top: '100%', left: 0, right: 0,
            maxHeight: 220, overflowY: 'auto',
            background: 'var(--ed-surface)', border: '1px solid var(--ed-border)', borderRadius: 6,
            boxShadow: '0 4px 16px rgba(0,0,0,0.12)', marginTop: 2,
          }}
        >
          {rows.map((row, ri) => {
            if (row.type === 'header') {
              return (
                <div key={`h-${row.domain}`} style={{
                  fontSize: 9, fontWeight: 700, color: 'var(--ed-text-3)', textTransform: 'uppercase',
                  letterSpacing: '0.06em', padding: '5px 10px 2px',
                  background: 'var(--ed-input-bg)', borderTop: ri === 0 ? 'none' : '1px solid var(--ed-divider-2)',
                }}>
                  {row.domain}
                </div>
              );
            }
            const isActive = row.idx === cursor;
            return (
              <div
                key={row.id}
                data-idx={row.idx}
                onMouseDown={() => select(row.id)}
                onMouseEnter={() => setCursor(row.idx)}
                style={{
                  padding: '5px 10px', fontSize: 12, cursor: 'pointer',
                  fontFamily: 'monospace',
                  background: isActive ? 'var(--ed-primary-soft)' : 'transparent',
                  color: 'var(--ed-text)',
                }}
              >
                {highlight(row.id, q)}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const inputStyle = {
  fontSize: 12, padding: '4px 6px', border: '1px solid var(--ed-border)', borderRadius: 4,
  background: 'var(--ed-input-bg)', width: '100%', boxSizing: 'border-box',
};
