import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { DEVICE_MODELS } from '../data/deviceModels';

const defaultDevice = DEVICE_MODELS[0];

function autoCell(device, orientation, columns, prevCellH) {
  // MQTTDash lays out in UIKit logical points, not physical pixels.
  // All iPads share the same 768×1024 pt logical canvas regardless of Retina scale.
  const [pw, ph] = device.points ?? [768, 1024];
  const screenW = orientation === 'landscape' ? ph : pw;
  const cellW = Math.floor(screenW / columns);
  return [cellW, prevCellH ?? cellW];
}

const initCellDims = autoCell(defaultDevice, 'portrait', 6, null);
const defaultGrid = {
  columns: 6,
  widget_dimensions: initCellDims,
  widget_margins: [5, 5],
  widget_size: [1, 1],
};

function newPage(name = 'Page') {
  return { id: `page_${Date.now()}`, name, widgets: [] };
}

/** Effective grid for a page — merges page-level override on top of top-level grid. */
export function effectiveGrid(topGrid, page) {
  return page?.grid ? { ...topGrid, ...page.grid } : topGrid;
}

export const useEditorStore = create(
  persist(
    (set) => ({
      device: defaultDevice,
      orientation: 'portrait',
      grid: { ...defaultGrid },
      pages: [newPage('Main')],
      activePageIndex: 0,
      selectedWidgetId: null,
      banner: '',
      navbar_edge: 'bottom',
      navbar_style: {},
      navbar_show_battery: true,
      navbar_show_keepawake: true,
      device_settings: { keep_awake: true, screensaver_timeout: 0 },
      history: [],
      future: [],

      // ── Device / orientation ───────────────────────────────────────────────
      setDevice: (device) => set((s) => {
        const oldH = s.grid.widget_dimensions[1];
        const dims = autoCell(device, s.orientation, s.grid.columns, oldH);
        return { device, grid: { ...s.grid, widget_dimensions: dims } };
      }),
      setOrientation: (orientation) => set((s) => {
        const oldH = s.grid.widget_dimensions[1];
        const dims = autoCell(s.device, orientation, s.grid.columns, oldH);
        return { orientation, grid: { ...s.grid, widget_dimensions: dims } };
      }),

      // ── Grid ───────────────────────────────────────────────────────────────
      setGridConfig: (patch) => set((s) => {
        const newCols = patch.columns ?? s.grid.columns;
        let newDims = patch.widget_dimensions ?? s.grid.widget_dimensions;
        if (patch.columns !== undefined && patch.widget_dimensions === undefined) {
          newDims = autoCell(s.device, s.orientation, newCols, s.grid.widget_dimensions[1]);
        }
        return {
          grid: { ...s.grid, ...patch, widget_dimensions: newDims },
          history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
          future: [],
        };
      }),

      // Per-page grid override (null patch clears the override)
      setPageGrid: (pageIndex, patch) => set((s) => {
        const pages = s.pages.map((p, i) => {
          if (i !== pageIndex) return p;
          if (patch === null) {
            const { grid: _, ...rest } = p;
            return rest;
          }
          return { ...p, grid: { ...(p.grid ?? {}), ...patch } };
        });
        return {
          pages,
          history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
          future: [],
        };
      }),

      // ── Pages ─────────────────────────────────────────────────────────────
      addPage: (name = 'New Page') => set((s) => ({
        pages: [...s.pages, newPage(name)],
        activePageIndex: s.pages.length,
        history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
        future: [],
      })),

      removePage: (index) => set((s) => {
        if (s.pages.length <= 1) return {};
        const pages = s.pages.filter((_, i) => i !== index);
        const activePageIndex = Math.min(s.activePageIndex, pages.length - 1);
        return {
          pages,
          activePageIndex,
          selectedWidgetId: null,
          history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
          future: [],
        };
      }),

      renamePage: (index, name) => set((s) => ({
        pages: s.pages.map((p, i) => i === index ? { ...p, name } : p),
      })),

      setActivePage: (index) => set({ activePageIndex: index, selectedWidgetId: null }),

      movePage: (from, to) => set((s) => {
        const pages = [...s.pages];
        const [moved] = pages.splice(from, 1);
        pages.splice(to, 0, moved);
        return {
          pages,
          activePageIndex: to,
          history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
          future: [],
        };
      }),

      // ── Widgets (always target active page) ───────────────────────────────
      selectWidget: (id) => set({ selectedWidgetId: id }),

      addWidget: (widget) => set((s) => ({
        pages: s.pages.map((p, i) => i === s.activePageIndex
          ? { ...p, widgets: [...p.widgets, widget] } : p),
        history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
        future: [],
      })),

      updateWidget: (id, patch) => set((s) => ({
        pages: s.pages.map((p, i) => i === s.activePageIndex
          ? { ...p, widgets: p.widgets.map(w => w.id === id ? { ...w, ...patch } : w) } : p),
        history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
        future: [],
      })),

      removeWidget: (id) => set((s) => ({
        pages: s.pages.map((p, i) => i === s.activePageIndex
          ? { ...p, widgets: p.widgets.filter(w => w.id !== id) } : p),
        selectedWidgetId: null,
        history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
        future: [],
      })),

      moveWidget: (id, x, y) => set((s) => ({
        pages: s.pages.map((p, i) => i === s.activePageIndex
          ? { ...p, widgets: p.widgets.map(w => w.id === id ? { ...w, x, y } : w) } : p),
        history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
        future: [],
      })),

      resizeWidget: (id, w, h) => set((s) => ({
        pages: s.pages.map((p, i) => i === s.activePageIndex
          ? { ...p, widgets: p.widgets.map(wi => wi.id === id ? { ...wi, w, h } : wi) } : p),
        history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
        future: [],
      })),

      // ── Misc ──────────────────────────────────────────────────────────────
      setBanner: (banner) => set({ banner }),
      setNavbarEdge: (navbar_edge) => set({ navbar_edge }),
      setNavbarStyle: (patch) => set((s) => {
        const next = { ...s.navbar_style, ...patch };
        // Remove keys explicitly set to undefined/null/empty
        Object.keys(next).forEach((k) => { if (!next[k]) delete next[k]; });
        return { navbar_style: next };
      }),
      setNavbarShowBattery: (v) => set({ navbar_show_battery: v }),
      setNavbarShowKeepAwake: (v) => set({ navbar_show_keepawake: v }),
      setDeviceSettings: (patch) => set((s) => ({ device_settings: { ...s.device_settings, ...patch } })),
      setWidgets: (widgets) => set((s) => ({  // used by import — replaces active page widgets
        pages: s.pages.map((p, i) => i === s.activePageIndex ? { ...p, widgets } : p),
      })),
      setPages: (pages) => set({ pages, activePageIndex: 0, selectedWidgetId: null }),

      undo: () => set((s) => {
        if (s.history.length === 0) return {};
        const prev = s.history[s.history.length - 1];
        return {
          grid: prev.grid,
          pages: prev.pages,
          history: s.history.slice(0, -1),
          future: [{ grid: s.grid, pages: s.pages }, ...s.future].slice(0, 50),
        };
      }),
      redo: () => set((s) => {
        if (s.future.length === 0) return {};
        const next = s.future[0];
        return {
          grid: next.grid,
          pages: next.pages,
          history: [...s.history, { grid: s.grid, pages: s.pages }].slice(-50),
          future: s.future.slice(1),
        };
      }),
      reset: () => set({
        device: defaultDevice,
        orientation: 'portrait',
        grid: { ...defaultGrid },
        pages: [newPage('Main')],
        activePageIndex: 0,
        selectedWidgetId: null,
        banner: '',
        navbar_edge: 'bottom',
        history: [],
        future: [],
      }),
    }),
    {
      name: 'mqttdash-editor-v4',
      partialize: (s) => ({
        device: s.device,
        orientation: s.orientation,
        grid: s.grid,
        pages: s.pages,
        banner: s.banner,
        navbar_edge: s.navbar_edge,
        navbar_show_battery: s.navbar_show_battery,
        navbar_show_keepawake: s.navbar_show_keepawake,
        device_settings: s.device_settings,
      }),
      merge: (persisted, current) => {
        const merged = { ...current, ...persisted };
        // Guard against missing or malformed pages from old data
        if (!Array.isArray(merged.pages) || merged.pages.length === 0) {
          merged.pages = current.pages;
        }
        if (typeof merged.activePageIndex !== 'number' || merged.activePageIndex >= merged.pages.length) {
          merged.activePageIndex = 0;
        }
        return merged;
      },
    }
  )
);
