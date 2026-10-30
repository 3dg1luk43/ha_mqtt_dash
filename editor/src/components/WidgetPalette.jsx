import { WIDGET_TYPES } from '../data/widgetTypes';
import { EMBEDDED } from '../utils/haEmbed';
import PaletteItem from './PaletteItem';

/**
 * Widget library. Variants:
 *  - list: classic full-width rows (standalone, wide)
 *  - grid: compact 2-column icon grid (inside HA, wide)
 *  - rail: ~56 px icon-only column (narrow); label in the tooltip
 */
export default function WidgetPalette({ variant = 'list' }) {
  const rail = variant === 'rail';
  const width = rail ? 56 : variant === 'grid' ? 184 : 220;
  // Inside HA the side panes are cards on the page background
  const card = EMBEDDED
    ? { borderRadius: 'var(--ed-radius)', border: '1px solid var(--ed-divider)' }
    : { borderRight: '1px solid var(--ed-divider)' };

  return (
    <aside style={{
      width,
      flexShrink: 0,
      background: 'var(--ed-surface)',
      ...card,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {!rail && (
        <div style={{ padding: variant === 'grid' ? '12px 12px 6px' : '12px 12px 8px', borderBottom: variant === 'grid' ? 'none' : '1px solid var(--ed-divider-2)', flexShrink: 0 }}>
          <h2 style={{ fontSize: variant === 'list' ? 14 : 'var(--ed-section-size)', fontWeight: 'var(--ed-section-weight)', margin: 0, color: 'var(--ed-section-color)', textTransform: 'var(--ed-section-transform)', letterSpacing: 'var(--ed-section-spacing)' }}>
            {variant === 'grid' ? 'Widgets' : 'Widget Library'}
          </h2>
          <p style={{ fontSize: 11, color: 'var(--ed-text-3)', margin: '2px 0 0' }}>Drag onto canvas</p>
        </div>
      )}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        overflowX: 'hidden',
        padding: rail ? '8px 0' : variant === 'grid' ? '4px 10px 10px' : 10,
        ...(variant === 'grid' && { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, alignContent: 'start' }),
        ...(rail && { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }),
      }}>
        {WIDGET_TYPES.map((t) => (
          <PaletteItem key={t.type} typeDef={t} variant={variant} />
        ))}
      </div>
    </aside>
  );
}
