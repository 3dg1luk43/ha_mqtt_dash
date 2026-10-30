import { useState } from 'react';
import { useEditorStore } from '../../store/editorStore';

export default function PageTabs({ fill = false }) {
  const { pages, activePageIndex, navbar_edge, navbar_style = {}, setActivePage, addPage, removePage, renamePage } = useEditorStore();
  const [editingIndex, setEditingIndex] = useState(null);
  const [editValue, setEditValue] = useState('');

  const isVertical = navbar_edge === 'left' || navbar_edge === 'right';

  function startRename(i, name) {
    setEditingIndex(i);
    setEditValue(name);
  }

  function commitRename() {
    if (editingIndex !== null && editValue.trim()) {
      renamePage(editingIndex, editValue.trim());
    }
    setEditingIndex(null);
  }

  function handleRemove(e, i) {
    e.stopPropagation();
    if (pages.length <= 1) return;
    const page = pages[i];
    if (page.widgets.length > 0 && !window.confirm(`Delete "${page.name}" and its ${page.widgets.length} widget(s)?`)) return;
    removePage(i);
  }

  // Colors matching iOS defaults (can be overridden via navbar_style)
  const navBg       = navbar_style.bgColor       || '#141414';
  const activeClr   = navbar_style.activeColor   || '#336ee6';
  const inactiveClr = navbar_style.inactiveColor || '#404040';
  const navTextClr  = navbar_style.textColor     || '#ffffff';
  const borderClr   = navbar_style.borderColor   || 'rgba(255,255,255,0.18)';

  const barStyle = isVertical ? {
    width: fill ? '100%' : 80,
    height: fill ? '100%' : '100%',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'stretch',
    padding: '6px 0',
    background: navBg,
    borderRight: navbar_edge === 'left' ? `1px solid ${borderClr}` : 'none',
    borderLeft: navbar_edge === 'right' ? `1px solid ${borderClr}` : 'none',
    flexShrink: 0,
    overflowY: 'auto',
  } : {
    height: fill ? '100%' : 44,
    width: fill ? '100%' : undefined,
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    padding: '4px 6px',
    background: navBg,
    borderTop: navbar_edge === 'bottom' ? `1px solid ${borderClr}` : 'none',
    borderBottom: navbar_edge === 'top' ? `1px solid ${borderClr}` : 'none',
    flexShrink: 0,
    overflowX: 'auto',
  };

  return (
    <div style={barStyle}>
      {pages.map((page, i) => {
        const isActive = i === activePageIndex;
        const tabStyle = isVertical ? {
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
          padding: '5px 4px',
          margin: '2px 4px',
          borderRadius: 6,
          background: isActive ? activeClr : inactiveClr,
          cursor: 'pointer',
          userSelect: 'none',
        } : {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 4,
          padding: '4px 8px',
          borderRadius: 6,
          background: isActive ? activeClr : inactiveClr,
          cursor: 'pointer',
          userSelect: 'none',
          flexShrink: 0,
          minWidth: 60,
        };

        return (
          <div
            key={page.id}
            onClick={() => setActivePage(i)}
            onDoubleClick={() => startRename(i, page.name)}
            style={tabStyle}
          >
            {editingIndex === i ? (
              <input
                autoFocus
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={commitRename}
                onKeyDown={(e) => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setEditingIndex(null); }}
                onClick={(e) => e.stopPropagation()}
                style={{ fontSize: 10, background: '#1a1c2e', color: '#fff', border: '1px solid #5c7aff', borderRadius: 3, padding: '1px 3px', width: isVertical ? 60 : 80 }}
              />
            ) : (
              <span style={{ fontSize: isVertical ? 10 : 12, color: navTextClr, fontWeight: isActive ? 600 : 400, textAlign: 'center', wordBreak: 'break-word', maxWidth: isVertical ? 64 : undefined }}>
                {page.name}
              </span>
            )}
            {pages.length > 1 && (
              <button
                onClick={(e) => handleRemove(e, i)}
                title="Delete page"
                style={{ border: 'none', background: 'none', color: 'rgba(255,255,255,0.45)', cursor: 'pointer', fontSize: 11, padding: '0 1px', lineHeight: 1 }}
              >
                ×
              </button>
            )}
          </div>
        );
      })}

      <button
        onClick={() => addPage(`Page ${pages.length + 1}`)}
        title="Add page"
        style={isVertical ? {
          border: `1px dashed ${borderClr}`, borderRadius: 6, background: 'none', color: 'rgba(255,255,255,0.4)',
          cursor: 'pointer', padding: '4px 2px', fontSize: 12, margin: '4px 6px', textAlign: 'center',
        } : {
          flexShrink: 0, border: `1px dashed ${borderClr}`, borderRadius: 6, background: 'none', color: 'rgba(255,255,255,0.4)',
          cursor: 'pointer', padding: '3px 10px', fontSize: 13, marginLeft: 2,
        }}
      >
        {isVertical ? '+' : '+ page'}
      </button>

      {!isVertical && (
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>
          Double-click to rename
        </span>
      )}
    </div>
  );
}
