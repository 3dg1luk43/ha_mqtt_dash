import { useState } from 'react';
import { useEditorStore } from '../../store/editorStore';
import { EMBEDDED } from '../../utils/haEmbed';
import GridConfigSection from './GridConfigSection';
import EntityManager from './EntityManager';
import CommonFields from './CommonFields';
import FormatFields from './FormatFields';
import SensorConfig from './widget_configs/SensorConfig';
import LabelConfig from './widget_configs/LabelConfig';
import ClockConfig from './widget_configs/ClockConfig';
import WeatherConfig from './widget_configs/WeatherConfig';
import ClimateConfig from './widget_configs/ClimateConfig';
import CameraConfig from './widget_configs/CameraConfig';
import PrinterConfig from './widget_configs/PrinterConfig';
import TimerConfig from './widget_configs/TimerConfig';
import WebpageConfig from './widget_configs/WebpageConfig';
import MealieConfig from './widget_configs/MealieConfig';
import SousvideConfig from './widget_configs/SousvideConfig';
import ApplianceConfig from './widget_configs/ApplianceConfig';
import LightConfig from './widget_configs/LightConfig';
import MediaPlayerConfig from './widget_configs/MediaPlayerConfig';
import CoverConfig from './widget_configs/CoverConfig';

const SENSOR_TYPES = ['sensor', 'value', 'person'];

/**
 * Right-hand config panel.
 *  mode 'side':   docked column (fixed 340 px standalone, clamp(280px, 24vw, 380px) inside HA)
 *  mode 'drawer': slide-over from the right edge (narrow layouts), shown while `open`
 */
export default function ConfigPanel({ mode = 'side', open = false, onClose }) {
  const { pages, activePageIndex, selectedWidgetId, updateWidget } = useEditorStore();
  const widgets = pages[activePageIndex]?.widgets ?? [];
  const selected = widgets.find((w) => w.id === selectedWidgetId);
  const [noSelTab, setNoSelTab] = useState('grid'); // 'grid' | 'entities'

  function handleChange(patch) {
    if (selected) updateWidget(selected.id, patch);
  }

  const drawer = mode === 'drawer';
  const inset = EMBEDDED ? 8 : 0;
  const frame = drawer
    ? {
        position: 'absolute', top: inset, right: inset, bottom: inset, zIndex: 60,
        width: EMBEDDED ? 'min(360px, calc(100% - 88px))' : 'min(340px, calc(100% - 64px))',
        boxShadow: 'var(--ed-shadow)',
        transform: open ? 'none' : 'translateX(calc(100% + 24px))',
        visibility: open ? 'visible' : 'hidden',
        ...(EMBEDDED ? { borderRadius: 'var(--ed-radius)', border: '1px solid var(--ed-divider)' } : { borderLeft: '1px solid var(--ed-divider)' }),
      }
    : EMBEDDED
      ? { width: 'clamp(280px, 24vw, 380px)', flexShrink: 0, borderRadius: 'var(--ed-radius)', border: '1px solid var(--ed-divider)' }
      : { width: 340, flexShrink: 0, borderLeft: '1px solid var(--ed-divider)' };

  return (
    <aside className={drawer ? 'ed-drawer' : undefined} aria-hidden={drawer && !open ? true : undefined} style={{
      ...frame,
      background: 'var(--ed-surface)',
      color: 'var(--ed-text)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--ed-divider-2)', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ ...panelTitle, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {selected ? `${getIcon(selected.type)} ${selected.type}` : EMBEDDED ? 'Settings' : 'Config Panel'}
          </h2>
          {selected && (
            <p style={{ fontSize: 11, color: 'var(--ed-text-3)', margin: '2px 0 0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {selected.label || selected.entity_id || 'unnamed'} · {selected.w}×{selected.h} cells
            </p>
          )}
        </div>
        {drawer && (
          <button
            className="ed-btn ed-icon-btn"
            onClick={onClose}
            title="Close panel"
            style={{ width: 30, height: 30, fontSize: 15 }}
          >✕</button>
        )}
      </div>

      {/* Tab bar — only when no widget selected */}
      {!selected && (
        <div style={{ display: 'flex', borderBottom: '1px solid var(--ed-divider-2)', flexShrink: 0 }}>
          {[['grid', '⚙ Grid'], ['entities', '🗂 Entities']].map(([t, lbl]) => (
            <button key={t} onClick={() => setNoSelTab(t)} style={{
              flex: 1, padding: EMBEDDED ? '10px 0' : '7px 0', fontSize: EMBEDDED ? 13 : 12, border: 'none', background: 'none', cursor: 'pointer',
              borderBottom: noSelTab === t ? '2px solid var(--ed-primary)' : '2px solid transparent',
              color: noSelTab === t ? 'var(--ed-primary)' : 'var(--ed-text-2)', fontWeight: noSelTab === t ? 600 : 400,
            }}>{lbl}</button>
          ))}
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {selected ? (
          <>
            <CommonFields widget={selected} onChange={handleChange} />
            <div style={divider} />
            <TypeConfig widget={selected} onChange={handleChange} />
            <div style={divider} />
            <FormatFields format={selected.format} onChange={(format) => handleChange({ format })} />
          </>
        ) : noSelTab === 'grid' ? (
          <GridConfigSection />
        ) : (
          <EntityManager />
        )}
      </div>
    </aside>
  );
}

function TypeConfig({ widget, onChange }) {
  const t = widget.type;
  if (t === 'light') return <LightConfig widget={widget} onChange={onChange} />;
  if (SENSOR_TYPES.includes(t)) return <SensorConfig widget={widget} onChange={onChange} />;
  if (t === 'label') return <LabelConfig widget={widget} onChange={onChange} />;
  if (t === 'clock') return <ClockConfig widget={widget} onChange={onChange} />;
  if (t === 'weather') return <WeatherConfig widget={widget} onChange={onChange} />;
  if (t === 'climate') return <ClimateConfig widget={widget} onChange={onChange} />;
  if (t === 'camera') return <CameraConfig widget={widget} onChange={onChange} />;
  if (t === 'printer') return <PrinterConfig widget={widget} onChange={onChange} />;
  if (t === 'timer') return <TimerConfig widget={widget} onChange={onChange} />;
  if (t === 'webpage') return <WebpageConfig widget={widget} onChange={onChange} />;
  if (t === 'mealie') return <MealieConfig widget={widget} onChange={onChange} />;
  if (t === 'sousvide') return <SousvideConfig widget={widget} onChange={onChange} />;
  if (t === 'appliance') return <ApplianceConfig widget={widget} onChange={onChange} />;
  if (t === 'mediaplayer') return <MediaPlayerConfig widget={widget} onChange={onChange} />;
  if (t === 'cover') return <CoverConfig widget={widget} onChange={onChange} />;
  return null;
}

function getIcon(type) {
  const icons = { light: '💡', switch: '🔀', scene: '🎬', sensor: '📟', value: '🔢', person: '🧑', button: '🔘', label: '🏷️', clock: '⏰', weather: '🌦️', climate: '🌡️', camera: '📷', printer: '🖨️', timer: '⏱️', webpage: '🌐', mealie: '🍽️', sousvide: '♨️', appliance: '🏠', mediaplayer: '🎵', cover: '🪟' };
  return icons[type] ?? '?';
}

const divider = { height: 1, background: 'var(--ed-divider-2)', margin: '12px 0' };
const panelTitle = {
  fontSize: EMBEDDED ? 14 : 13, fontWeight: EMBEDDED ? 500 : 600, margin: 0, color: 'var(--ed-text)',
  textTransform: EMBEDDED ? 'capitalize' : 'uppercase', letterSpacing: EMBEDDED ? 0 : '0.05em',
};
