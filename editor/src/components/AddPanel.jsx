// Left pane: add cards. Search finds Home Assistant entities by name; drag or
// click one and the matching card is added. Without a search, the card types
// are listed by group. Narrow layouts get an icon rail that opens the full pane.
import { useMemo, useState } from 'react';
import { useDraggable } from '@dnd-kit/core';
import { mdiMagnify, mdiClose } from '@mdi/js';
import { WIDGET_TYPES, GROUPS, typeDef, cardTypeForEntity } from '../data/widgetTypes';
import { useHaEntities, searchEntities } from '../utils/haEmbed';
import { Icon, IconButton } from './ui';

const MAX_RESULTS = 60;

export default function AddPanel({ variant = 'panel', onAdd }) {
  const [expanded, setExpanded] = useState(false);
  if (variant === 'rail' && !expanded) {
    return (
      <aside className="ed-pane" style={{ width: 60, alignItems: 'center', padding: '8px 0', gap: 2, overflowY: 'auto' }}>
        <IconButton path={mdiMagnify} title="Find an entity" onClick={() => setExpanded(true)} />
        <div style={{ width: 28, height: 1, background: 'var(--ed-divider)', margin: '6px 0' }} />
        {WIDGET_TYPES.filter((t) => !t.hidden).map((t) => (
          <DragSource key={t.type} id={`rail-${t.type}`} data={{ dragType: 'new', widgetType: t.type }} onAdd={onAdd}
            className="ed-rail-item" title={`${t.label}: ${t.description}`}>
            <Icon path={t.icon} size={22} />
          </DragSource>
        ))}
      </aside>
    );
  }
  const overlay = variant === 'rail';
  return (
    <aside className="ed-pane" style={overlay
      ? { position: 'absolute', top: 8, left: 8, bottom: 8, width: 'min(320px, calc(100% - 16px))', zIndex: 70, boxShadow: 'var(--ed-shadow)' }
      : { width: 'clamp(240px, 19vw, 300px)' }}>
      <FullPanel onAdd={(d) => { onAdd(d); if (overlay) setExpanded(false); }} onClose={overlay ? () => setExpanded(false) : null} />
    </aside>
  );
}

function FullPanel({ onAdd, onClose }) {
  const [query, setQuery] = useState('');
  const entities = useHaEntities((s) => s.entities);
  const results = useMemo(() => (query.trim() ? searchEntities(entities, query).slice(0, MAX_RESULTS) : []), [entities, query]);
  const typeHits = query.trim()
    ? WIDGET_TYPES.filter((t) => !t.hidden && `${t.label} ${t.type}`.toLowerCase().includes(query.trim().toLowerCase()))
    : [];

  return (
    <>
      <div className="ed-pane-head" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h2 className="ed-pane-title" style={{ flex: 1 }}>Add a card</h2>
          {onClose && <IconButton path={mdiClose} title="Close" onClick={onClose} />}
        </div>
        <label className="ed-search">
          <Icon path={mdiMagnify} size={20} />
          <input autoFocus={!!onClose} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search entities" aria-label="Search entities" />
          {query && <IconButton path={mdiClose} size={16} title="Clear" className="ed-icon-btn--sm" onClick={() => setQuery('')} />}
        </label>
      </div>
      <div className="ed-pane-body" style={{ paddingTop: 0 }}>
        {query.trim() ? (
          <>
            {typeHits.length > 0 && <TypeList types={typeHits} onAdd={onAdd} title="Card types" />}
            <div className="ed-group-title">Entities</div>
            {results.length === 0 && <div className="ed-hint">No entity matches “{query.trim()}”.</div>}
            {results.map((e) => {
              const type = cardTypeForEntity(e.id);
              const def = typeDef(type);
              return (
                <DragSource key={e.id} id={`ent-${e.id}`} data={{ dragType: 'entity', entityId: e.id, name: e.name, widgetType: type }}
                  onAdd={onAdd} className="ed-add-item" title={`Add a ${def.label.toLowerCase()} card for ${e.id}`}>
                  <span className="ed-add-icon"><Icon path={def.icon} size={18} /></span>
                  <span className="ed-add-text">
                    <div className="ed-add-name">{e.name}</div>
                    <div className="ed-add-meta">{e.id} · {def.label}</div>
                  </span>
                </DragSource>
              );
            })}
          </>
        ) : (
          <>
            <p className="ed-hint" style={{ margin: '12px 0 0' }}>Drag a card onto the panel, or click to add it in the first free spot.</p>
            {GROUPS.map((g) => (
              <TypeList key={g.key} title={g.label} onAdd={onAdd}
                types={WIDGET_TYPES.filter((t) => !t.hidden && t.group === g.key)} />
            ))}
          </>
        )}
      </div>
    </>
  );
}

function TypeList({ title, types, onAdd }) {
  return (
    <>
      <div className="ed-group-title">{title}</div>
      {types.map((t) => (
        <DragSource key={t.type} id={`pal-${t.type}`} data={{ dragType: 'new', widgetType: t.type }} onAdd={onAdd}
          className="ed-add-item" title={t.description}>
          <span className="ed-add-icon"><Icon path={t.icon} size={18} /></span>
          <span className="ed-add-text">
            <div className="ed-add-name">{t.label}</div>
            <div className="ed-add-meta">{t.description}</div>
          </span>
        </DragSource>
      ))}
    </>
  );
}

/** Draggable onto the canvas; a plain click (no drag) adds it in the first free spot. */
function DragSource({ id, data, onAdd, className, title, children }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id, data });
  return (
    <div ref={setNodeRef} {...listeners} {...attributes} role="button" tabIndex={0}
      className={className} title={title} data-dragging={isDragging || undefined}
      onClick={() => onAdd(data)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onAdd(data); } }}>
      {children}
    </div>
  );
}
