import { useState, useEffect, useRef } from 'react';
import { DndContext, DragOverlay, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { useEditorStore, effectiveGrid } from './store/editorStore';
import { pixelToCell, tileGeometry } from './utils/gridLayout';
import { getFrameDims, getNavOffset, fitScale } from './utils/frameGeometry';
import { useHaEntities } from './utils/haEmbed';
import { findFreeSpot, makeWidget, defaultSize } from './utils/placement';
import { useLayout } from './utils/useLayout';

import Header from './components/Header';
import AddPanel from './components/AddPanel';
import GridCanvas from './components/Canvas/GridCanvas';
import WidgetPreview from './components/Canvas/WidgetPreview';
import ConfigPanel from './components/ConfigPanel/ConfigPanel';
import ProfileDialog from './components/ProfileDialog';
import HelpDialog from './components/HelpDialog';

import './App.css';

const typing = (el) => el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable);

export default function App() {
  const [dialog, setDialog] = useState(null); // 'profile' | 'help'
  const { addWidget, moveWidget, pages, activePageIndex, grid, device, orientation, navbar_edge, undo, redo, selectedWidgetId, selectWidget, removeWidget } = useEditorStore();
  const page = pages[activePageIndex];
  const widgets = page?.widgets ?? [];
  const pageGrid = effectiveGrid(grid, page);
  const layout = useLayout();

  useEffect(() => { useHaEntities.getState().load(); }, []);

  // Settings drawer (narrow layouts): opens when a card gets selected and closes
  // again on deselect, unless it was opened with the toolbar toggle.
  const [cfg, setCfg] = useState({ open: false, bySel: false, sel: selectedWidgetId });
  if (cfg.sel !== selectedWidgetId) {
    setCfg(selectedWidgetId
      ? { open: true, bySel: cfg.open ? cfg.bySel : true, sel: selectedWidgetId }
      : { open: cfg.open && !cfg.bySel, bySel: false, sel: selectedWidgetId });
  }
  const toggleConfig = () => setCfg((c) => ({ ...c, open: !c.open, bySel: false }));
  const closeConfig = () => setCfg((c) => ({ ...c, open: false, bySel: false }));

  const [activeItem, setActiveItem] = useState(null);
  const [dropPreview, setDropPreview] = useState(null);
  const canvasAreaRef = useRef(null);
  const [canvasSize, setCanvasSize] = useState({ w: 900, h: 700 });

  useEffect(() => {
    if (!canvasAreaRef.current) return undefined;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setCanvasSize({ w: e.contentRect.width, h: e.contentRect.height });
    });
    ro.observe(canvasAreaRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    function onKey(e) {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return; }
      if (mod && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) { e.preventDefault(); redo(); return; }
      if (typing(document.activeElement) || dialog) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedWidgetId) { e.preventDefault(); removeWidget(selectedWidgetId); }
      if (e.key === 'Escape' && selectedWidgetId) selectWidget(null);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undo, redo, selectedWidgetId, removeWidget, selectWidget, dialog]);

  // Click in the add panel: first free spot on the current page
  function addAtFreeSpot(data) {
    const [w, h] = defaultSize(data);
    const spot = findFreeSpot(widgets, w, h, pageGrid.columns);
    const widget = makeWidget(data, spot);
    addWidget(widget);
    selectWidget(widget.id);
  }

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));
  const getCanvasScale = () => fitScale(device, orientation, canvasSize.w, canvasSize.h);

  function dragSize(data) {
    if (data.dragType === 'move') {
      const wi = widgets.find((x) => x.id === data.widgetId);
      return wi ? [wi.w, wi.h] : [1, 1];
    }
    const [w, h] = defaultSize(data);
    return [Math.min(w, pageGrid.columns), h];
  }

  function dropCell(event) {
    // over.rect is the visual ClientRect of the scaled droppable frame
    const { over, delta, active } = event;
    if (!over) return null;
    const { bezelLeft, bezelTop } = getFrameDims(device, orientation);
    const scale = getCanvasScale();
    const finalX = (event.activatorEvent?.clientX ?? 0) + delta.x;
    const finalY = (event.activatorEvent?.clientY ?? 0) + delta.y;
    const screenLeft = over.rect.left + bezelLeft * scale;
    const screenTop = over.rect.top + bezelTop * scale;
    const navOff = getNavOffset(navbar_edge);
    let px = (finalX - screenLeft) / scale - navOff.x;
    let py = (finalY - screenTop) / scale - navOff.y;
    // Moving: keep the grab point, so the card's top-left lands where it looks like it does
    const data = active?.data?.current;
    if (data?.dragType === 'move') {
      const wi = widgets.find((x) => x.id === data.widgetId);
      if (wi) {
        const geo = tileGeometry(wi, pageGrid);
        px -= (event.activatorEvent.clientX - screenLeft) / scale - navOff.x - geo.left;
        py -= (event.activatorEvent.clientY - screenTop) / scale - navOff.y - geo.top;
      }
    }
    return pixelToCell(px, py, pageGrid);
  }

  function handleDragStart(event) {
    setActiveItem(event.active.data.current);
    setDropPreview(null);
  }

  function handleDragMove(event) {
    const data = event.active.data.current;
    const cell = event.over && data ? dropCell(event) : null;
    if (!cell) { setDropPreview(null); return; }
    const [w, h] = dragSize(data);
    setDropPreview((prev) => (prev?.x === cell.x && prev?.y === cell.y && prev?.w === w && prev?.h === h ? prev : { x: cell.x, y: cell.y, w, h }));
  }

  function handleDragEnd(event) {
    setActiveItem(null);
    setDropPreview(null);
    const data = event.active.data.current;
    const cell = event.over && data ? dropCell(event) : null;
    if (!cell) return;
    if (data.dragType === 'move') { moveWidget(data.widgetId, cell.x, cell.y); return; }
    const [w, h] = dragSize(data);
    const widget = makeWidget(data, { x: cell.x, y: cell.y, w, h });
    addWidget(widget);
    selectWidget(widget.id);
  }

  function renderDragPreview() {
    if (!activeItem) return null;
    const scale = getCanvasScale();
    const [w, h] = dragSize(activeItem);
    const preview = activeItem.dragType === 'move'
      ? widgets.find((x) => x.id === activeItem.widgetId)
      : makeWidget(activeItem, { x: 0, y: 0, w, h });
    if (!preview) return null;
    const tileW = w * pageGrid.widget_dimensions[0] * scale;
    const tileH = h * pageGrid.widget_dimensions[1] * scale;
    return (
      <div style={{
        width: tileW, height: tileH, background: preview.format?.bgColor || '#23243a', borderRadius: 8,
        border: '2px solid var(--ed-primary)', opacity: 0.85, boxShadow: '0 4px 20px #0005', overflow: 'hidden',
        pointerEvents: 'none', position: 'relative',
      }}>
        <WidgetPreview widget={preview} tileW={tileW} tileH={tileH} />
      </div>
    );
  }

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragMove={handleDragMove} onDragEnd={handleDragEnd}>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--ed-bg)', color: 'var(--ed-text)', fontFamily: 'var(--ed-font)' }}>
        <Header
          onProfile={() => setDialog('profile')}
          onHelp={() => setDialog('help')}
          layout={layout}
          configToggle={layout.configMode === 'drawer' ? { open: cfg.open, onToggle: toggleConfig } : null}
        />
        <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden', position: 'relative', gap: 8, padding: 8 }}>
          <AddPanel variant={layout.paletteVariant} onAdd={addAtFreeSpot} />
          <main ref={canvasAreaRef} style={{ flex: 1, minWidth: 0, overflow: 'hidden', background: 'var(--ed-canvas-bg)', position: 'relative' }}>
            <GridCanvas containerWidth={canvasSize.w} containerHeight={canvasSize.h} dropPreview={dropPreview} />
          </main>
          <ConfigPanel mode={layout.configMode} open={cfg.open} onClose={closeConfig} />
        </div>
      </div>
      <DragOverlay>{renderDragPreview()}</DragOverlay>
      {dialog === 'profile' && <ProfileDialog onClose={() => setDialog(null)} />}
      {dialog === 'help' && <HelpDialog onClose={() => setDialog(null)} />}
    </DndContext>
  );
}
