// Right pane: the selected card's settings, or the layout when nothing is selected.
//  mode 'side':   docked column
//  mode 'drawer': slides over the canvas on narrow layouts, shown while `open`
import { mdiClose, mdiViewDashboardOutline } from '@mdi/js';
import { useEditorStore } from '../../store/editorStore';
import { typeDef } from '../../data/widgetTypes';
import { entityName } from '../../utils/haEmbed';
import WidgetSettings from './WidgetSettings';
import LayoutSettings from './LayoutSettings';
import { Icon, IconButton } from '../ui';

export default function ConfigPanel({ mode = 'side', open = false, onClose }) {
  const { pages, activePageIndex, selectedWidgetId } = useEditorStore();
  const selected = (pages[activePageIndex]?.widgets ?? []).find((w) => w.id === selectedWidgetId);
  const def = selected && typeDef(selected.type);
  const drawer = mode === 'drawer';

  const frame = drawer
    ? {
        position: 'absolute', top: 8, right: 8, bottom: 8, zIndex: 60, width: 'min(380px, calc(100% - 88px))',
        boxShadow: 'var(--ed-shadow)', transform: open ? 'none' : 'translateX(calc(100% + 24px))', visibility: open ? 'visible' : 'hidden',
      }
    : { width: 'clamp(300px, 24vw, 380px)' };

  const sub = selected
    ? [def?.label ?? selected.type, selected.entity_id && (entityName(selected.entity_id) ?? selected.entity_id)].filter(Boolean).join(' · ')
    : `Page: ${pages[activePageIndex]?.name ?? ''}`;

  return (
    <aside className={`ed-pane ${drawer ? 'ed-drawer' : ''}`} aria-hidden={drawer && !open ? true : undefined} style={frame}>
      <div className="ed-pane-head">
        <span className="ed-add-icon"><Icon path={def?.icon ?? mdiViewDashboardOutline} size={18} /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 className="ed-pane-title">{selected ? (selected.label || def?.label) : 'Layout'}</h2>
          <div className="ed-pane-sub">{sub}</div>
        </div>
        {drawer && <IconButton path={mdiClose} title="Close" onClick={onClose} />}
      </div>
      <div className="ed-pane-body">
        {selected ? <WidgetSettings key={selected.id} widget={selected} /> : <LayoutSettings />}
      </div>
    </aside>
  );
}
