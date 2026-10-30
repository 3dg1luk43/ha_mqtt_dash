// Grid layout math — mirrors exact MQTTDash app calculations

/**
 * Compute pixel geometry for a widget tile on the canvas.
 * @param {object} widget  - { x, y, w, h }
 * @param {object} grid    - { widget_dimensions, widget_margins }
 * @returns {{ left, top, width, height }} in px
 */
export function tileGeometry(widget, grid) {
  const cellW = grid.widget_dimensions[0];
  const cellH = grid.widget_dimensions[1];
  const marginX = grid.widget_margins[0];
  const marginY = grid.widget_margins[1];

  return {
    left: widget.x * cellW + marginX,
    top: widget.y * cellH + marginY,
    width: widget.w * cellW - 2 * marginX,
    height: widget.h * cellH - 2 * marginY,
  };
}

/**
 * Convert a pixel offset (relative to canvas top-left) to a grid cell {x, y}.
 * Clamps to valid range. Returns floored cell.
 */
export function pixelToCell(px, py, grid) {
  const cellW = grid.widget_dimensions[0];
  const cellH = grid.widget_dimensions[1];
  return {
    x: Math.max(0, Math.floor(px / cellW)),
    y: Math.max(0, Math.floor(py / cellH)),
  };
}

/**
 * Check whether two widgets overlap on the grid.
 */
export function widgetsOverlap(a, b) {
  return (
    a.x < b.x + b.w &&
    a.x + a.w > b.x &&
    a.y < b.y + b.h &&
    a.y + a.h > b.y
  );
}

/**
 * Find all widgets that overlap with the given widget (excluding itself).
 */
export function findOverlaps(widget, allWidgets) {
  return allWidgets.filter(
    (w) => w.id !== widget.id && widgetsOverlap(widget, w)
  );
}

/**
 * Total canvas pixel dimensions based on grid settings.
 * Width = columns * cellW, Height = rows (auto, just enough to show all widgets).
 */
export function canvasSize(grid, widgets) {
  const cellW = grid.widget_dimensions[0];
  const cellH = grid.widget_dimensions[1];
  const cols = grid.columns;

  const maxRow = widgets.reduce((m, w) => Math.max(m, w.y + w.h), 8);
  return {
    width: cols * cellW,
    height: maxRow * cellH,
  };
}
