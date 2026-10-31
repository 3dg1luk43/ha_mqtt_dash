// New cards: what they contain and where they go.
import { typeDef, cardTypeForEntity } from '../data/widgetTypes';

/** First top-left cell where a w×h card fits without overlapping, scanning row by row. */
export function findFreeSpot(widgets, w, h, columns) {
  const cols = Math.max(1, columns);
  const width = Math.min(w, cols);
  const busy = (x, y) => widgets.some((o) => x < o.x + o.w && x + width > o.x && y < o.y + o.h && y + h > o.y);
  const maxY = widgets.reduce((m, o) => Math.max(m, o.y + o.h), 0);
  for (let y = 0; y <= maxY; y++) {
    for (let x = 0; x + width <= cols; x++) if (!busy(x, y)) return { x, y, w: width, h };
  }
  return { x: 0, y: maxY, w: width, h };
}

/** Card for a palette type, or for an HA entity (type picked from its domain). */
export function makeWidget({ widgetType, entityId, name }, cell) {
  const type = widgetType ?? cardTypeForEntity(entityId);
  const def = typeDef(type);
  const [w, h] = cell.w ? [cell.w, cell.h] : (def?.size ?? [1, 1]);
  const widget = {
    id: `${type}_${Date.now().toString(36)}`,
    type,
    label: name ?? def?.label ?? type,
    entity_id: '',
    x: cell.x, y: cell.y, w, h,
    format: {},
  };
  if (entityId) {
    if (type === 'camera') { widget.camera_entity = entityId; widget.camera_source = 'entity'; } else widget.entity_id = entityId;
  }
  return widget;
}

export const defaultSize = (data) => typeDef(data.widgetType ?? cardTypeForEntity(data.entityId))?.size ?? [1, 1];
