import { useRef } from 'react';
import { useDraggable } from '@dnd-kit/core';
import { tileGeometry } from '../../utils/gridLayout';
import { mdiClose } from '@mdi/js';
import WidgetPreview from './WidgetPreview';
import { Icon } from '../ui';

// iOS app default colors (matched from DashboardViewController.m)
const CARD_BG = '#1c1f26';
// Types drawn with the iPad card design: dark card, 12px corners.
const CARD_TYPES = new Set(['light', 'climate', 'timer', 'camera', 'printer', 'printer3d', 'appliance', 'mediaplayer', 'sousvide', 'mealie']);

const TYPE_BG = {
  light:  (fmt) => fmt.offBgColor || CARD_BG,
  switch: (fmt) => fmt.offBgColor || '#333347',
  scene:  (fmt) => fmt.offBgColor || '#333333',   // rgba(0.20, 0.20, 0.20)
  button: (fmt) => fmt.bgColor    || '#594040',   // rgba(0.35, 0.25, 0.25)
};

export default function WidgetTile({ widget, grid, isSelected, hasOverlap, onSelect, onResize, onDelete }) {
  const geo = tileGeometry(widget, grid);

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: widget.id,
    data: { dragType: 'move', widgetId: widget.id },
  });

  // Resize handle
  const resizeRef = useRef(null);
  const resizeState = useRef(null);

  function onResizePointerDown(e) {
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    resizeState.current = {
      startX: e.clientX,
      startY: e.clientY,
      origW: widget.w,
      origH: widget.h,
    };
  }

  function onResizePointerMove(e) {
    if (!resizeState.current) return;
    const cellW = grid.widget_dimensions[0];
    const cellH = grid.widget_dimensions[1];
    const dx = e.clientX - resizeState.current.startX;
    const dy = e.clientY - resizeState.current.startY;
    const newW = Math.max(1, resizeState.current.origW + Math.round(dx / cellW));
    const newH = Math.max(1, resizeState.current.origH + Math.round(dy / cellH));
    onResize(widget.id, newW, newH);
  }

  function onResizePointerUp() {
    resizeState.current = null;
  }

  const fmt = widget.format ?? {};
  const typeBgFn = TYPE_BG[widget.type];
  // iOS default tile bg: rgba(0.18, 0.18, 0.18) = #2e2e2e; editor keeps the dark-blue default
  const isCard = CARD_TYPES.has(widget.type);
  const background = typeBgFn ? typeBgFn(fmt) : (fmt.bgColor || (isCard ? CARD_BG : '#23243a'));

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClick={(e) => { e.stopPropagation(); onSelect(widget.id); }}
      style={{
        position: 'absolute',
        left: geo.left,
        top: geo.top,
        width: geo.width,
        height: geo.height,
        background,
        borderRadius: isCard ? 12 : 8,
        border: isSelected
          ? '2px solid #4fc3f7'
          : hasOverlap
          ? '2px solid #ef5350'
          : '1px solid rgba(255,255,255,0.08)',
        cursor: isDragging ? 'grabbing' : 'grab',
        opacity: isDragging ? 0.4 : 1,
        overflow: 'hidden',
        boxSizing: 'border-box',
        userSelect: 'none',
        zIndex: isSelected ? 10 : 1,
      }}
    >
      <WidgetPreview widget={widget} tileW={geo.width} tileH={geo.height} />

      {/* Overlap badge */}
      {hasOverlap && (
        <span style={{
          position: 'absolute', top: 2, left: 4,
          fontSize: 9, color: '#ef5350',
          background: '#200000', padding: '1px 3px', borderRadius: 3,
          pointerEvents: 'none',
        }}>
          overlap
        </span>
      )}

      {/* Remove button, shown on hover */}
      <button
        className="widget-delete-btn"
        title="Remove card"
        aria-label="Remove card"
        onClick={(e) => { e.stopPropagation(); onDelete(widget.id); }}
        style={{
          position: 'absolute', top: 3, right: 3, width: 18, height: 18, borderRadius: '50%',
          border: 'none', background: 'rgba(0,0,0,0.55)', color: '#fff', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0,
        }}
      >
        <Icon path={mdiClose} size={12} />
      </button>

      {/* Resize handle */}
      <div
        ref={resizeRef}
        onPointerDown={onResizePointerDown}
        onPointerMove={onResizePointerMove}
        onPointerUp={onResizePointerUp}
        style={{
          position: 'absolute', bottom: 0, right: 0,
          width: 14, height: 14,
          cursor: 'se-resize',
          background: 'rgba(255,255,255,0.15)',
          borderRadius: '4px 0 4px 0',
        }}
      />
    </div>
  );
}
