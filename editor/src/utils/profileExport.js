// Profile JSON <-> editor state (multi-page schema; the old flat one still loads)

const WIDGET_EXTRA_KEYS = [
  'unit', 'text', 'time_pattern', 'stream_url', 'scale_mode', 'overlay_button',
  'attrs', 'attr_units', 'modes', 'state_formats',
  'nozzle_entity', 'bed_entity', 'time_entity', 'progress_entity', 'status_entity',
  'progress_unit', 'visible_rows',
  'default_seconds',  // timer
  'mealie_url', 'mealie_api_key', 'recipe_slug', 'visible_section',  // mealie
  'configurable',  // timer
  'temp_entity', 'target_entity', 'program_entity',  // sousvide / appliance extra entities
  'dimmable',  // light: false hides brightness slider (default true)
  'cover_items', 'cover_controls', 'cover_layout', 'position_presets',  // cover
  'camera_entity', 'refresh_interval',  // camera: HA-relayed camera.* entity, frame interval (s)
  'nozzle_target_entity', 'bed_target_entity', 'preview_entity', 'layer_entity', 'total_layers_entity',  // printer
  'phase_entity',  // appliance (progress_entity shared with printer)
  'temp_step',  // climate
  'presets',  // timer: quick-pick durations in seconds
  'show_art',  // mediaplayer: false hides album art (default true)
];

// Array-valued keys: exported only when non-empty.
const ARRAY_KEYS = new Set(['attrs', 'modes', 'visible_rows', 'cover_controls', 'cover_items', 'position_presets', 'presets']);

function exportWidget(w) {
  const out = { id: w.id, type: w.type };
  if (w.entity_id) out.entity_id = w.entity_id;
  if (w.label) out.label = w.label;
  out.x = w.x; out.y = w.y; out.w = w.w; out.h = w.h;
  if (w.protected) out.protected = true;
  // preview_value is editor-only — never exported to the profile

  // camera_source is editor-only: emit only the field for the selected source.
  const skip = w.type === 'camera' && w.camera_source === 'url' ? 'camera_entity'
    : w.type === 'camera' && w.camera_source === 'entity' ? 'stream_url' : null;

  for (const key of WIDGET_EXTRA_KEYS) {
    if (key === skip) continue;
    if (key === 'overlay_button') {
      if (w.overlay_button?.entity_id) out.overlay_button = { ...w.overlay_button };
    } else if (ARRAY_KEYS.has(key)) {
      if (w[key]?.length > 0) out[key] = w[key];
    } else if (key === 'attr_units' || key === 'state_formats') {
      if (w[key] && Object.keys(w[key]).length > 0) out[key] = { ...w[key] };
    } else if (key === 'show_art') {
      if (w.show_art === false) out.show_art = false;  // true is the implicit default
    } else if (key === 'cover_layout') {
      if (w[key] && w[key] !== 'auto') out[key] = w[key];  // 'auto' is the implicit default
    } else {
      if (w[key] != null && w[key] !== '') out[key] = w[key];
    }
  }

  if (w.format && Object.keys(w.format).length > 0) out.format = { ...w.format };
  return out;
}

function exportGrid(grid) {
  return {
    columns: grid.columns,
    widget_dimensions: grid.widget_dimensions,
    widget_margins: grid.widget_margins,
    widget_size: grid.widget_size ?? [1, 1],
  };
}

/**
 * Build the new multi-page profile JSON accepted by HA.
 */
export function buildProfile(state) {
  // Panel behaviour (keep awake, screensaver, brightness, orientation) lives in
  // the panel's Home Assistant entities, not in the profile.
  const profile = {};
  profile.ui = {
    navbar_edge: state.navbar_edge ?? 'bottom',
    grid: exportGrid(state.grid),
    pages: (state.pages ?? []).map((page) => {
      const p = { name: page.name, widgets: page.widgets.map(exportWidget) };
      if (page.grid) p.grid = exportGrid(page.grid);
      return p;
    }),
  };
  if (state.navbar_style && Object.keys(state.navbar_style).length > 0) {
    profile.ui.navbar_style = { ...state.navbar_style };
  }
  if (state.navbar_show_battery === false) profile.ui.navbar_show_battery = false;
  if (state.navbar_show_keepawake === false) profile.ui.navbar_show_keepawake = false;

  return profile;
}

/**
 * Parse a JSON string — returns { ok, data } or { ok: false, error }.
 */
export function parseProfile(jsonStr) {
  try {
    const parsed = JSON.parse(jsonStr);
    const hasNew = parsed.ui && (Array.isArray(parsed.ui?.pages) || Array.isArray(parsed.ui?.widgets));
    const hasOld = parsed.grid && Array.isArray(parsed.widgets);
    if (!hasNew && !hasOld) {
      return { ok: false, error: 'Missing required fields: expected ui.pages or (grid + widgets)' };
    }
    return { ok: true, data: parsed };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/**
 * Convert a parsed profile (old or new format) into store-compatible state.
 */
export function profileToState(profile) {
  // New format: profile.ui.pages
  if (profile.ui) {
    const ui = profile.ui;
    const grid = normaliseGrid(ui.grid ?? {});

    let pages;
    if (Array.isArray(ui.pages) && ui.pages.length > 0) {
      pages = ui.pages.map((p, i) => ({
        id: `page_${Date.now()}_${i}`,
        name: p.name ?? `Page ${i + 1}`,
        widgets: (p.widgets ?? []).map(tagWidget),
        ...(p.grid ? { grid: normaliseGrid(p.grid) } : {}),
      }));
    } else if (Array.isArray(ui.widgets)) {
      // Single-page fallback inside ui
      pages = [{ id: `page_${Date.now()}`, name: 'Main', widgets: ui.widgets.map(tagWidget) }];
    } else {
      pages = [{ id: `page_${Date.now()}`, name: 'Main', widgets: [] }];
    }

    return {
      grid,
      pages,
      navbar_edge: ui.navbar_edge ?? 'bottom',
      navbar_style: (ui.navbar_style && typeof ui.navbar_style === 'object') ? ui.navbar_style : {},
      navbar_show_battery: ui.navbar_show_battery !== false,
      navbar_show_keepawake: ui.navbar_show_keepawake !== false,
    };
  }

  // Old flat format: { banner, grid, widgets }
  const grid = normaliseGrid(profile.grid ?? {});
  const widgets = (profile.widgets ?? []).map(tagWidget);
  return {
    grid,
    pages: [{ id: `page_${Date.now()}`, name: 'Main', widgets }],
  };
}

function normaliseGrid(g) {
  return {
    columns: g.columns ?? 6,
    widget_dimensions: g.widget_dimensions ?? [120, 120],
    widget_margins: g.widget_margins ?? [5, 5],
    widget_size: g.widget_size ?? [1, 1],
  };
}

function tagWidget(w, i) {
  return { ...w, id: w.id || `widget_${Date.now()}_${i}` };
}
