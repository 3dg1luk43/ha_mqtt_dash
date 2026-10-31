// Entity field: type a name or an entity id; suggestions come from Home
// Assistant (friendly name + id), limited to `domains` when given. Free text is
// kept, so entities that don't exist yet can still be entered.
import { useEffect, useMemo, useRef, useState } from 'react';
import { useHaEntities, searchEntities } from '../../utils/haEmbed';

const MAX = 80;

export default function EntityPicker({ value, onChange, placeholder = 'Search by name or entity id', domains }) {
  const entities = useHaEntities((s) => s.entities);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(null); // null: show the current value
  const [cursor, setCursor] = useState(0);
  const listRef = useRef(null);

  const text = query ?? value ?? '';
  const matches = useMemo(() => {
    const q = query ?? '';
    const scoped = searchEntities(entities, q, domains);
    return (scoped.length || !domains?.length ? scoped : searchEntities(entities, q)).slice(0, MAX);
  }, [entities, query, domains]);
  const known = entities.find((e) => e.id === value);

  function pick(id) {
    onChange(id);
    setQuery(null);
    setOpen(false);
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') { setOpen(true); setCursor((c) => Math.min(c + 1, matches.length - 1)); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { setCursor((c) => Math.max(c - 1, 0)); e.preventDefault(); }
    else if (e.key === 'Enter' && open && matches[cursor]) { pick(matches[cursor].id); e.preventDefault(); }
    else if (e.key === 'Escape') { setOpen(false); setQuery(null); }
  }

  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${cursor}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [cursor]);

  return (
    <div className="ed-picker">
      <input className="ed-input ed-input--mono" value={text} placeholder={placeholder} spellCheck={false}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); setCursor(0); if (e.target.value.includes('.')) onChange(e.target.value.trim()); }}
        onFocus={() => { setOpen(true); setCursor(0); }}
        onBlur={() => setTimeout(() => {
          setOpen(false);
          if (query != null && query.trim() !== (value ?? '')) onChange(query.trim());
          setQuery(null);
        }, 150)}
        onKeyDown={onKey} />
      {known && !open && <div className="ed-hint" style={{ marginTop: 4 }}>{known.name}</div>}
      {open && (
        <div className="ed-picker-list" ref={listRef}>
          {matches.length === 0 && <div className="ed-picker-empty">No matching entity. The text is used as typed.</div>}
          {matches.map((e, i) => (
            <div key={e.id} data-idx={i} data-active={i === cursor} className="ed-picker-item"
              onMouseDown={(ev) => { ev.preventDefault(); pick(e.id); }} onMouseEnter={() => setCursor(i)}>
              <span className="ed-picker-name">{e.name}</span>
              <span className="ed-picker-id">{e.id}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
