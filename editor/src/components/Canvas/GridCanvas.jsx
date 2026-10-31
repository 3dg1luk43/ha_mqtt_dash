import { useDroppable } from '@dnd-kit/core';
import { useEditorStore, effectiveGrid } from '../../store/editorStore';
import DeviceFrame from './DeviceFrame';
import GridOverlay from './GridOverlay';
import WidgetTile from './WidgetTile';
import PageTabs from './PageTabs';
import { findOverlaps, tileGeometry } from '../../utils/gridLayout';
import { NAV_H, NAV_W, getFrameDims, fitScale } from '../../utils/frameGeometry';

// Absolute-position style for the nav bar strip inside the screen.
function navBarStyle(navbar_edge) {
  const base = { position: 'absolute', zIndex: 20, overflow: 'hidden' };
  switch (navbar_edge) {
    case 'top':    return { ...base, top: 0, left: 0, right: 0, height: NAV_H };
    case 'bottom': return { ...base, bottom: 0, left: 0, right: 0, height: NAV_H };
    case 'left':   return { ...base, top: 0, left: 0, bottom: 0, width: NAV_W };
    case 'right':  return { ...base, top: 0, right: 0, bottom: 0, width: NAV_W };
    default:       return { display: 'none' };
  }
}

// Absolute-position style for the widget content area (screen minus nav bar).
function contentAreaStyle(navbar_edge) {
  const base = { position: 'absolute', overflow: 'hidden' };
  switch (navbar_edge) {
    case 'top':    return { ...base, top: NAV_H, left: 0, right: 0, bottom: 0 };
    case 'bottom': return { ...base, top: 0, left: 0, right: 0, bottom: NAV_H };
    case 'left':   return { ...base, top: 0, left: NAV_W, right: 0, bottom: 0 };
    case 'right':  return { ...base, top: 0, left: 0, right: NAV_W, bottom: 0 };
    default:       return { ...base, inset: 0 };
  }
}

export default function GridCanvas({ containerWidth, containerHeight, dropPreview }) {
  const { grid, pages, activePageIndex, selectedWidgetId, selectWidget, resizeWidget, removeWidget, device, orientation, navbar_edge } = useEditorStore();

  const activePage = pages[activePageIndex] ?? pages[0];
  const widgets = activePage?.widgets ?? [];
  const pageGrid = effectiveGrid(grid, activePage);

  const { screenW, screenH, frameW, frameH } = getFrameDims(device, orientation);

  const scale = fitScale(device, orientation, containerWidth, containerHeight);

  // Content area dimensions in logical points
  const isVerticalNav = navbar_edge === 'left' || navbar_edge === 'right';
  const contentW = isVerticalNav ? screenW - NAV_W : screenW;
  const contentH = isVerticalNav ? screenH : screenH - NAV_H;

  const { setNodeRef, isOver } = useDroppable({ id: 'grid-canvas' });

  const overlappingIds = new Set();
  widgets.forEach((w) => {
    if (findOverlaps(w, widgets).length > 0) overlappingIds.add(w.id);
  });

  return (
    // Centered in the canvas area; the wrapper reserves the scaled size so the
    // frame fits both width and height (the droppable keeps its visual rect).
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      overflow: 'hidden',
    }}>
      <div style={{ width: frameW * scale, height: frameH * scale, position: 'relative', flexShrink: 0 }}>
      <div
        ref={setNodeRef}
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          transformOrigin: 'top left',
          transform: `scale(${scale})`,
          width: frameW,
          height: frameH,
          outline: isOver ? '3px solid #4fc3f7' : 'none',
          borderRadius: 40 * (device.scale ?? 1),
        }}
        onClick={() => selectWidget(null)}
      >
        <DeviceFrame screenW={screenW} screenH={screenH} orientation={orientation}>

          {/* Navigation bar rendered inside the screen at the correct edge */}
          <div style={navBarStyle(navbar_edge)}>
            <PageTabs fill />
          </div>

          {/* Widget content area — offset from screen origin by the nav bar */}
          <div style={contentAreaStyle(navbar_edge)}>
            <GridOverlay grid={pageGrid} width={contentW} height={contentH} />

            {dropPreview && (() => {
              const geo = tileGeometry(dropPreview, pageGrid);
              return (
                <div style={{
                  position: 'absolute',
                  left: geo.left,
                  top: geo.top,
                  width: geo.width,
                  height: geo.height,
                  background: 'rgba(79,195,247,0.18)',
                  border: '2px dashed #4fc3f7',
                  borderRadius: 6,
                  pointerEvents: 'none',
                  zIndex: 5,
                }} />
              );
            })()}

            {widgets.length === 0 && !dropPreview && (
              <div className="ed-empty-hint">
                <strong>This page is empty.</strong><br />
                Search for an entity on the left and drag it here, or press Load to start from what the panel shows now.
              </div>
            )}
            {widgets.map((w) => (
              <WidgetTile
                key={w.id}
                widget={w}
                grid={pageGrid}
                isSelected={w.id === selectedWidgetId}
                hasOverlap={overlappingIds.has(w.id)}
                onSelect={selectWidget}
                onResize={resizeWidget}
                onDelete={removeWidget}
              />
            ))}
          </div>

        </DeviceFrame>
      </div>
      </div>
    </div>
  );
}
