import { useState, useEffect, useRef } from 'react';
import { DndContext, DragOverlay, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { useEditorStore } from './store/editorStore';
import { WIDGET_TYPES } from './data/widgetTypes';
import { pixelToCell, tileGeometry } from './utils/gridLayout';
import { getFrameDims, getNavOffset, fitScale } from './utils/frameGeometry';
import { parseProfile, profileToState } from './utils/profileExport';
import { EMBEDDED, listEntityIds } from './utils/haEmbed';

import Header from './components/Header';
import DeviceSelector from './components/DeviceSelector';
import WidgetPreview from './components/Canvas/WidgetPreview';
import WidgetPalette from './components/WidgetPalette';
import GridCanvas from './components/Canvas/GridCanvas';
import ConfigPanel from './components/ConfigPanel/ConfigPanel';
import ImportExportModal from './components/ImportExport/ImportExportModal';
import WelcomeModal from './components/WelcomeModal';
import { useEntityStore } from './store/entityStore';
import { useLayout } from './utils/useLayout';

import './App.css';

const WELCOME_KEY = 'mqttdash-welcomed-v1';

export default function App() {
  const [modal, setModal] = useState(null);
  // Inside Home Assistant the JSON-export tutorial doesn't apply — skip it
  const [showWelcome, setShowWelcome] = useState(() => !EMBEDDED && !localStorage.getItem(WELCOME_KEY));
  const { addWidget, moveWidget, pages, activePageIndex, grid, device, orientation, navbar_edge, undo, redo, setGridConfig, setPages, setBanner, setNavbarEdge, setNavbarShowBattery, setNavbarShowKeepAwake, setDeviceSettings, selectedWidgetId } = useEditorStore();
  const widgets = pages[activePageIndex]?.widgets ?? [];
  const layout = useLayout();

  // Config drawer (narrow layouts): opens when a widget gets selected and closes
  // again on deselect — unless the user opened it with the toolbar toggle.
  const [cfg, setCfg] = useState({ open: false, bySel: false, sel: selectedWidgetId });
  if (cfg.sel !== selectedWidgetId) {
    setCfg(selectedWidgetId
      ? { open: true, bySel: cfg.open ? cfg.bySel : true, sel: selectedWidgetId }
      : { open: cfg.open && !cfg.bySel, bySel: false, sel: selectedWidgetId });
  }
  const toggleConfig = () => setCfg((c) => ({ ...c, open: !c.open, bySel: false }));
  const closeConfig = () => setCfg((c) => ({ ...c, open: false, bySel: false }));

  // Auto-import shared profile from URL hash
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash.startsWith('#profile=')) return;
    try {
      // Reverse URL-safe base64: restore + and / then re-pad to multiple of 4
      const raw = hash.slice('#profile='.length).replace(/-/g, '+').replace(/_/g, '/');
      const padded = raw + '='.repeat((4 - raw.length % 4) % 4);
      const json = decodeURIComponent(atob(padded));
      const result = parseProfile(json);
      if (result.ok) {
        const s = profileToState(result.data);
        setGridConfig(s.grid);
        setPages(s.pages);
        setBanner(s.banner ?? '');
        if (s.navbar_edge) setNavbarEdge(s.navbar_edge);
        setNavbarShowBattery(s.navbar_show_battery !== false);
        setNavbarShowKeepAwake(s.navbar_show_keepawake !== false);
        if (s.device_settings) setDeviceSettings(s.device_settings);
      }
    } catch { /* ignore malformed share links */ }
    history.replaceState(null, '', window.location.pathname);
  }, []);

  // Embedded in HA: keep the entity autocomplete list in sync automatically
  useEffect(() => {
    if (!EMBEDDED) return;
    listEntityIds().then((ids) => useEntityStore.getState().bulkAdd(ids.join('\n'))).catch(() => {});
  }, []);

  const entities = useEntityStore((s) => s.entities);
  const [activeItem, setActiveItem] = useState(null);
  const [dropPreview, setDropPreview] = useState(null);

  function closeWelcome() {
    localStorage.setItem(WELCOME_KEY, '1');
    setShowWelcome(false);
  }

  const canvasAreaRef = useRef(null);
  const [canvasSize, setCanvasSize] = useState({ w: 900, h: 700 });

  useEffect(() => {
    if (!canvasAreaRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        setCanvasSize({ w: e.contentRect.width, h: e.contentRect.height });
      }
    });
    ro.observe(canvasAreaRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    function handler(e) {
      if (e.ctrlKey && e.key === 'z') { e.preventDefault(); undo(); }
      if (e.ctrlKey && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) { e.preventDefault(); redo(); }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [undo, redo]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  function handleDragStart(event) {
    setActiveItem(event.active.data.current);
    setDropPreview(null);
  }

  function handleDragMove(event) {
    if (!event.over) { setDropPreview(null); return; }
    const data = event.active.data.current;
    if (!data) return;
    const cell = dropCell(event);
    if (!cell) { setDropPreview(null); return; }
    let w = 1, h = 1;
    if (data.dragType === 'move') {
      const wi = widgets.find((x) => x.id === data.widgetId);
      if (wi) { w = wi.w; h = wi.h; }
    }
    setDropPreview((prev) => {
      if (prev?.x === cell.x && prev?.y === cell.y && prev?.w === w && prev?.h === h) return prev;
      return { x: cell.x, y: cell.y, w, h };
    });
  }

  function getCanvasScale() {
    return fitScale(device, orientation, canvasSize.w, canvasSize.h);
  }

  function dropCell(event) {
    // Use over.rect — the actual visual ClientRect of the scaled droppable frame div.
    const { over, delta, active } = event;
    if (!over) return null;

    const { bezelLeft, bezelTop } = getFrameDims(device, orientation);
    const scale = getCanvasScale();

    const overRect = over.rect;
    const finalX = (event.activatorEvent?.clientX ?? 0) + delta.x;
    const finalY = (event.activatorEvent?.clientY ?? 0) + delta.y;

    // Screen origin in screen-space
    const screenLeft = overRect.left + bezelLeft * scale;
    const screenTop  = overRect.top  + bezelTop  * scale;

    // Nav bar offset: widget content area starts after the nav bar
    const navOff = getNavOffset(navbar_edge);
    let px = (finalX - screenLeft) / scale - navOff.x;
    let py = (finalY - screenTop)  / scale - navOff.y;

    // For move drags: offset by grab position so widget top-left aligns to drop cell.
    const data = active?.data?.current;
    if (data?.dragType === 'move') {
      const wi = widgets.find((x) => x.id === data.widgetId);
      if (wi) {
        const pageGrid = pages[activePageIndex]?.grid ?? grid;
        const geo = tileGeometry(wi, pageGrid);
        const grabX = (event.activatorEvent.clientX - screenLeft) / scale - navOff.x - geo.left;
        const grabY = (event.activatorEvent.clientY - screenTop)  / scale - navOff.y - geo.top;
        px -= grabX;
        py -= grabY;
      }
    }

    return pixelToCell(px, py, grid);
  }

  function handleDragEnd(event) {
    setActiveItem(null);
    setDropPreview(null);
    const { active, over } = event;
    if (!over) return;

    const data = active.data.current;
    if (!data) return;

    const cell = dropCell(event);
    if (!cell) return;

    if (data.dragType === 'new') {
      const typeDef = WIDGET_TYPES.find((t) => t.type === data.widgetType);
      addWidget({
        id: `${data.widgetType}_${Date.now()}`,
        type: data.widgetType,
        label: typeDef?.label ?? data.widgetType,
        entity_id: '',
        x: cell.x,
        y: cell.y,
        w: 1,
        h: 1,
        format: {},
      });
    } else if (data.dragType === 'move') {
      moveWidget(data.widgetId, cell.x, cell.y);
    }
  }

  function renderDragPreview() {
    if (!activeItem) return null;
    const csScale = getCanvasScale();
    const cellW = grid.widget_dimensions[0] * csScale;
    const cellH = grid.widget_dimensions[1] * csScale;

    let tileW, tileH, bgColor;

    let previewWidget;

    if (activeItem.dragType === 'new') {
      const t = WIDGET_TYPES.find((x) => x.type === activeItem.widgetType);
      tileW = cellW; tileH = cellH;
      bgColor = '#23243a';
      previewWidget = {
        type: activeItem.widgetType,
        label: t?.label ?? activeItem.widgetType,
        format: {},
      };
    } else if (activeItem.dragType === 'move') {
      const wi = widgets.find((x) => x.id === activeItem.widgetId);
      if (!wi) return null;
      tileW = wi.w * cellW; tileH = wi.h * cellH;
      bgColor = wi.format?.bgColor || '#23243a';
      previewWidget = wi;
    } else {
      return null;
    }

    return (
      <div style={{
        width: tileW, height: tileH,
        background: bgColor,
        borderRadius: 8,
        border: '2px solid #4fc3f7',
        opacity: 0.82,
        boxShadow: '0 4px 20px #0005',
        overflow: 'hidden',
        pointerEvents: 'none',
        boxSizing: 'border-box',
        position: 'relative',
      }}>
        <WidgetPreview widget={previewWidget} tileW={tileW} tileH={tileH} />
      </div>
    );
  }

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragMove={handleDragMove} onDragEnd={handleDragEnd}>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--ed-bg)', color: 'var(--ed-text)', fontFamily: 'var(--ed-font)' }}>
        <Header
          onImport={() => setModal('import')}
          onExport={() => setModal('export')}
          onHelp={() => setShowWelcome(true)}
          layout={layout}
          configToggle={layout.configMode === 'drawer' ? { open: cfg.open, onToggle: toggleConfig } : null}
        />
        {/* Inside HA the device model / orientation live in the toolbar */}
        {!EMBEDDED && <DeviceSelector />}

        <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden', position: 'relative', gap: EMBEDDED ? 8 : 0, padding: EMBEDDED ? 8 : 0 }}>
          <WidgetPalette variant={layout.paletteVariant} />
          <main ref={canvasAreaRef} style={{ flex: 1, minWidth: 0, overflow: 'hidden', background: 'var(--ed-canvas-bg)', position: 'relative' }}>
            <GridCanvas
              containerWidth={canvasSize.w}
              containerHeight={canvasSize.h}
              dropPreview={dropPreview}
            />
          </main>
          <ConfigPanel mode={layout.configMode} open={cfg.open} onClose={closeConfig} />
        </div>
      </div>

      <DragOverlay>{renderDragPreview()}</DragOverlay>
      {modal && <ImportExportModal mode={modal} onClose={() => setModal(null)} />}
      {showWelcome && <WelcomeModal onClose={closeWelcome} />}


      {/* Global entity autocomplete list — referenced by all entity_id inputs */}
      <datalist id="entity-autocomplete">
        {entities.map((e) => <option key={e} value={e} />)}
      </datalist>
    </DndContext>
  );
}
