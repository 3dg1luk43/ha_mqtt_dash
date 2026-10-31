import { mdiCctv, mdiPrinter3dNozzleOutline, mdiWeb, mdiMusicNote, mdiRefresh, mdiCheck, mdiShuffleVariant, mdiRepeat, mdiVolumeHigh, mdiSpeaker } from '@mdi/js';
import { typeDef as findType } from '../../data/widgetTypes';
import { Icon } from '../ui';

// Simulated values for each unit type — makes sensors look realistic in the preview
const MOCK_VALUES_BY_UNIT = {
  '°C': '21.5', '°F': '70.7', '%': '65', 'W': '1,240', 'kW': '3.2',
  'kWh': '12.4', 'V': '230', 'A': '5.4', 'lx': '450', 'ppm': '412',
  'hPa': '1013', 'mbar': '1013', 'km/h': '18', 'm/s': '5', 'mph': '11',
  'mm': '0.2', 'L': '142', 'L/min': '8.4', 'dB': '42', 'μg/m³': '8',
};

function formatTimePattern(pattern, date) {
  const h24 = date.getHours();
  const h12 = h24 % 12 || 12;
  const mm = String(date.getMinutes()).padStart(2, '0');
  const ss = String(date.getSeconds()).padStart(2, '0');
  const ampm = h24 >= 12 ? 'PM' : 'AM';
  return (pattern || 'HH:MM:SS')
    .replace('HH', String(h24).padStart(2, '0'))
    .replace('H', String(h24))
    .replace('hh', String(h12).padStart(2, '0'))
    .replace('h', String(h12))
    .replace('MM', mm)
    .replace('SS', ss)
    .replace('A', ampm)
    .replace('a', ampm.toLowerCase());
}

const MOCK_WEATHER_ATTRS = {
  temperature: '18', humidity: '65', wind_speed: '12',
  pressure: '1013', feels_like: '16', uv_index: '3',
  wind_bearing: '245', visibility: '10',
};

const MOCK_PRINTER = {
  nozzle:   ['Nozzle',   '215', '°C'],
  bed:      ['Bed',      '60',  '°C'],
  time:     ['Time',     '01:23', ''],
  progress: ['Progress', '45',  '%'],
  status:   ['Status',   'Printing', ''],
};

// ---- sub-renderers --------------------------------------------------------

function TitleLabel({ text }) {
  return (
    <span style={{
      color: '#9e9e9e', fontSize: '11px', fontWeight: 'bold',
      lineHeight: '14px', overflow: 'hidden', textOverflow: 'ellipsis',
      whiteSpace: 'nowrap', width: '100%', flexShrink: 0,
    }}>
      {text}
    </span>
  );
}

// ---- iPad card-design helpers (light, climate, timer, camera, printer,
// appliance, mediaplayer). Sizes are in device points, like the tile.

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const tint = (color, pct) => `color-mix(in srgb, ${color} ${pct}%, transparent)`;
const CARD_GRAY = '#8b919c';
const ACCENT = { green: '#3ecf6e', blue: '#4da3ff', amber: '#ffb547', orange: '#ff8a3d' };
const MODE_COLORS = { heat: ACCENT.orange, cool: ACCENT.blue, auto: ACCENT.green, dry: '#e5c04f', fan_only: '#7fd1d1', heat_cool: '#c38bff', off: '#6b7280' };
const COOK_GREEN = '#34C77B';
const CARD_HI = '#262A33';
const TEXT_DIM = '#5c6470';
const MODE_STATE = { heat: 'Heating', cool: 'Cooling', auto: 'Auto', dry: 'Drying', fan_only: 'Fan', heat_cool: 'Heat/Cool', off: 'Off' };

// Shared card metrics derived from the tile size.
function cardMetrics(tileW, tileH) {
  const m = Math.min(tileW, tileH);
  const pad = clamp(m * 0.08, 6, 14);
  const hdrFs = clamp(m * 0.1, 10, 13);
  return { m, pad, hdrFs, iw: tileW - pad * 2, ih: tileH - pad * 2 };
}

function Chip({ text, color, fs, bgPct = 22 }) {
  return (
    <span style={{
      background: tint(color, bgPct), color, fontSize: fs, fontWeight: 600,
      padding: `1px ${Math.round(fs * 0.6)}px`, borderRadius: fs, lineHeight: 1.4,
      whiteSpace: 'nowrap', flexShrink: 0,
    }}>{text}</span>
  );
}

function CardHeader({ label, fs, chip, chipColor, chipBgPct, right }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, minHeight: fs * 1.45 }}>
      <span style={{
        flex: 1, minWidth: 0, color: CARD_GRAY, fontSize: fs, fontWeight: 600, lineHeight: 1.3,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>{label}</span>
      {chip && <Chip text={chip} color={chipColor} fs={Math.max(8, fs - 2)} bgPct={chipBgPct} />}
      {right}
    </div>
  );
}

function Bar({ pct, color, h = 4 }) {
  return (
    <div style={{ height: h, borderRadius: h, background: 'rgba(255,255,255,0.1)', overflow: 'hidden', flexShrink: 0 }}>
      <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: h }} />
    </div>
  );
}

function BulbIcon({ size, color }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: 'block' }}>
      <path d="M12 2.5a6.5 6.5 0 0 0-3.9 11.7c.6.5.9 1.1.9 1.8v.5h6v-.5c0-.7.3-1.3.9-1.8A6.5 6.5 0 0 0 12 2.5z" fill={color} />
      <rect x="9" y="17.6" width="6" height="1.8" rx="0.9" fill={color} />
      <rect x="10" y="20.2" width="4" height="1.6" rx="0.8" fill={color} />
    </svg>
  );
}

// Same geometry as iOS _mpIconPath.
function TransportIcon({ type, size, color = 'rgba(255,255,255,0.85)' }) {
  const cx = size / 2, cy = size / 2;
  const iconH = size * 0.48;
  const triW = iconH * 0.84;
  const barW = Math.max(2, iconH * 0.20);
  const barGap = Math.max(2, iconH * 0.14);
  let path;
  if (type === 'play') {
    const x0 = cx - triW * 0.42, y0 = cy - iconH / 2;
    path = `M${x0},${y0} L${cx + triW * 0.58},${cy} L${x0},${cy + iconH / 2} Z`;
  } else if (type === 'next') {
    const x0 = cx - (triW + barGap + barW) / 2, y0 = cy - iconH / 2;
    path = `M${x0},${y0} L${x0 + triW},${cy} L${x0},${y0 + iconH} Z M${x0 + triW + barGap},${y0} h${barW} v${iconH} h${-barW} Z`;
  } else { // prev
    const x0 = cx - (barW + barGap + triW) / 2, y0 = cy - iconH / 2;
    const tx = x0 + barW + barGap;
    path = `M${x0},${y0} h${barW} v${iconH} h${-barW} Z M${tx + triW},${y0} L${tx},${cy} L${tx + triW},${y0 + iconH} Z`;
  }
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      <path d={path} fill={color} />
    </svg>
  );
}

// Placeholder album art.
const ART_BG = 'linear-gradient(135deg, #e0567a 0%, #7b4fd6 55%, #2d6cdf 100%)';

// ---- Mealie preview data / helpers ------------------------------------

const MEALIE_SAMPLES = [
  { name: 'Pasta Carbonara',      tags: ['Italian', 'Quick'] },
  { name: 'Chicken Tikka Masala', tags: ['Indian'] },
  { name: 'Greek Salad',          tags: ['Vegetarian'] },
  { name: 'Beef Stir Fry',        tags: ['Asian', 'Quick'] },
  { name: 'Lemon Risotto',        tags: ['Italian'] },
  { name: 'Fish Tacos',           tags: ['Mexican', 'Quick'] },
  { name: 'Shakshuka',            tags: ['Vegetarian', 'Breakfast'] },
  { name: 'Banana Bread',         tags: ['Baking'] },
];
const MEALIE_INGREDIENTS = [
  '400 g spaghetti', '150 g guanciale, diced', '4 egg yolks',
  '50 g pecorino romano, grated', 'Black pepper', 'Salt',
];
const MEALIE_STEPS = [
  'Boil the spaghetti in well-salted water until al dente.',
  'Crisp the guanciale in a dry pan over medium heat.',
  'Whisk the yolks with pecorino and plenty of pepper.',
  'Off the heat, toss pasta with guanciale and the egg mix, loosening with pasta water.',
];

// Same hash as iOS MealieTagColor (64-bit djb2-xor, HSB 0.55 / 0.95).
function mealieTagColor(tag) {
  let h = BigInt(5381);
  for (let i = 0; i < tag.length; i++) h = BigInt.asUintN(64, h * BigInt(33)) ^ BigInt(tag.charCodeAt(i));
  const hue = Number(h % BigInt(360)) / 60;
  const s = 0.55, v = 0.95, c = v * s, x = c * (1 - Math.abs((hue % 2) - 1)), m = v - c;
  const [r, g, b] = hue < 1 ? [c, x, 0] : hue < 2 ? [x, c, 0] : hue < 3 ? [0, c, x]
    : hue < 4 ? [0, x, c] : hue < 5 ? [x, 0, c] : [c, 0, x];
  return `rgb(${Math.round((r + m) * 255)}, ${Math.round((g + m) * 255)}, ${Math.round((b + m) * 255)})`;
}

const lineClamp = (n) => ({ display: '-webkit-box', WebkitLineClamp: n, WebkitBoxOrient: 'vertical', overflow: 'hidden' });

// ---- main component -------------------------------------------------------

/**
 * Renders a faithful iOS-app preview of a widget tile.
 * tileW / tileH are the outer pixel dimensions of the tile (including any border).
 */
export default function WidgetPreview({ widget, tileW, tileH }) {
  const { type, format = {} } = widget;
  const textColor = format.textColor || '#e0e0e0';
  const align = format.align || 'center';
  const vAlign = format.vAlign || 'middle';
  const displayLabel = widget.label || widget.entity_id || type;

  const jc = (a) => a === 'left' ? 'flex-start' : a === 'right' ? 'flex-end' : 'center';
  const colStyle = {
    display: 'flex', flexDirection: 'column',
    width: '100%', height: '100%',
    overflow: 'hidden', padding: '4px 6px',
    boxSizing: 'border-box',
  };

  // inner content height after padding
  const IH = tileH - 8;
  const IW = tileW - 12;

  switch (type) {

    // ---- stateful on/off buttons -----------------------------------------
    // Light: amber fill rises with brightness (left→right on wide tiles).
    case 'light': {
      const { m, pad } = cardMetrics(tileW, tileH);
      const dimmable = widget.dimmable !== false;
      const pct = dimmable ? 70 : 100;
      const fill = format.onBgColor || ACCENT.amber;
      const onText = format.onTextColor || '#2a1c05';
      const wide = tileW > 1.3 * tileH;
      const labelFs = format.textSize ? Number(format.textSize) : clamp(m * 0.13, 11, 18);
      const icon = clamp(m * 0.24, 18, 40);
      return (
        <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', left: 0, bottom: 0, background: fill,
            ...(wide ? { top: 0, width: `${pct}%` } : { right: 0, height: `${pct}%` }),
          }} />
          <div style={{
            position: 'absolute', top: pad, left: pad, width: icon, height: icon, borderRadius: '50%',
            background: 'rgba(0,0,0,0.22)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <BulbIcon size={icon * 0.62} color={fill} />
          </div>
          <div style={{ position: 'absolute', left: pad, right: pad, bottom: pad, color: onText, lineHeight: 1.2 }}>
            <div style={{ fontSize: labelFs, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {displayLabel}
            </div>
            <div style={{ fontSize: Math.max(9, labelFs * 0.78), opacity: 0.75, whiteSpace: 'nowrap' }}>
              {dimmable ? `On · ${pct}%` : 'On'}
            </div>
          </div>
        </div>
      );
    }

    case 'switch':
    case 'scene':
    case 'button': {
      const textSize = format.textSize
        ? `${format.textSize}px`
        : `${Math.max(13, Math.min(20, IH * 0.32))}px`;
      const va = vAlign === 'top' ? 'flex-start' : vAlign === 'bottom' ? 'flex-end' : 'center';

      return (
        <div style={{ ...colStyle, alignItems: jc(align), justifyContent: va }}>
          <span style={{
            color: textColor, fontSize: textSize,
            fontWeight: 'bold', textAlign: align, lineHeight: 1.25,
          }}>
            {displayLabel}
          </span>
        </div>
      );
    }

    // ---- sensor / value / person -----------------------------------------
    case 'sensor':
    case 'value':
    case 'person': {
      const unit = widget.unit || '';
      const mockValue =
        widget.preview_value != null ? widget.preview_value
        : type === 'person' ? 'home'
        : (MOCK_VALUES_BY_UNIT[unit] || '—');
      const baseSize = format.textSize
        ? Number(format.textSize)
        : Math.max(18, Math.min(36, IH * 0.44));
      const unitSize = baseSize * 0.5;

      return (
        <div style={colStyle}>
          <TitleLabel text={displayLabel} />
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: jc(align), minHeight: 0 }}>
            <span style={{ color: textColor, fontSize: `${baseSize}px`, fontWeight: 'bold', lineHeight: 1 }}>
              {mockValue}
            </span>
            {unit && (
              <span style={{
                color: textColor, fontSize: `${unitSize}px`,
                marginLeft: 4, lineHeight: 1,
              }}>
                {unit}
              </span>
            )}
          </div>
        </div>
      );
    }

    // ---- static label ----------------------------------------------------
    case 'label': {
      const lblText = widget.text || displayLabel;
      const lblSize = format.textSize
        ? `${format.textSize}px`
        : `${Math.max(13, Math.min(22, IH * 0.3))}px`;
      const va = vAlign === 'top' ? 'flex-start' : vAlign === 'bottom' ? 'flex-end' : 'center';
      return (
        <div style={{
          width: '100%', height: '100%',
          display: 'flex', alignItems: va, justifyContent: jc(align),
          padding: '4px 6px', boxSizing: 'border-box',
        }}>
          <span style={{ color: textColor, fontSize: lblSize, fontWeight: 'bold', textAlign: align, wordBreak: 'break-word', lineHeight: 1.3 }}>
            {lblText}
          </span>
        </div>
      );
    }

    // ---- clock -----------------------------------------------------------
    case 'clock': {
      const timeStr = formatTimePattern(widget.time_pattern, new Date());
      const clockSize = format.textSize
        ? `${format.textSize}px`
        : `${Math.max(16, Math.min(36, IH * 0.46))}px`;
      return (
        <div style={{
          width: '100%', height: '100%', padding: '4px 6px',
          boxSizing: 'border-box', display: 'flex',
          alignItems: 'center', justifyContent: jc(align),
        }}>
          <span style={{
            color: textColor, fontSize: clockSize, fontWeight: 'bold',
            fontVariantNumeric: 'tabular-nums', textAlign: align,
          }}>
            {timeStr}
          </span>
        </div>
      );
    }

    // ---- weather ---------------------------------------------------------
    case 'weather': {
      const attrs = widget.attrs || [];
      const attrUnits = widget.attr_units || {};
      const mainSize = format.textSize
        ? `${format.textSize}px`
        : `${Math.max(14, Math.min(22, IH * 0.26))}px`;
      const titleH = widget.label ? 14 : 0;
      const mainH = Math.max(14, IH * 0.28);
      const maxRows = Math.floor((IH - titleH - mainH - 4) / 15);

      return (
        <div style={colStyle}>
          {widget.label && <TitleLabel text={widget.label} />}
          <span style={{
            color: textColor, fontSize: mainSize, fontWeight: 'bold',
            textAlign: 'center', lineHeight: 1.3, flexShrink: 0,
          }}>
            sunny
          </span>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 1 }}>
            {attrs.slice(0, maxRows).map((attr, i) => {
              const unit = attrUnits[attr] || '';
              const val = MOCK_WEATHER_ATTRS[attr] || '--';
              return (
                <div key={i} style={{ color: 'rgba(255,255,255,0.8)', fontSize: '11px', textAlign: 'center', lineHeight: '15px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {attr.replace(/_/g, ' ')}: {val}{unit ? ` ${unit}` : ''}
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    // ---- climate ---------------------------------------------------------
    case 'climate': {
      const { pad, hdrFs, iw, ih } = cardMetrics(tileW, tileH);
      const modes = (widget.modes?.length ? widget.modes : ['off', 'heat', 'cool', 'auto']).slice(0, 6);
      const stateFormats = widget.state_formats || {};
      const active = modes.includes('heat') ? 'heat' : modes[0];
      const activeColor = stateFormats[active]?.bgColor || MODE_COLORS[active] || ACCENT.orange;
      const gap = clamp(ih * 0.05, 3, 8);
      const pillH = clamp(ih * 0.17, 16, 30);
      const pillFs = clamp(pillH * 0.42, 8, 12);
      const bodyH = ih - hdrFs * 1.45 - pillH - gap * 2;
      // Wide tiles: current temp left, stepper right. Square/tall: stacked.
      const side = iw >= 170 && iw > ih * 1.4;
      const curFs = format.textSize ? Number(format.textSize)
        : side ? clamp(Math.min(bodyH * 0.62, iw * 0.15), 16, 60) : clamp(Math.min(bodyH * 0.4, iw * 0.26), 14, 60);
      const sb = clamp(side ? Math.min(bodyH * 0.34, iw * 0.09) : Math.min(bodyH * 0.3, iw * 0.2), 14, 36);
      const tgtFs = clamp(sb * 0.62, 10, 22);
      const stepBtn = (sym) => (
        <div style={{
          width: sb, height: sb, borderRadius: '50%', background: 'rgba(255,255,255,0.1)', color: '#d8dbe0',
          fontSize: sb * 0.62, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>{sym}</div>
      );

      return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap, padding: pad, boxSizing: 'border-box', overflow: 'hidden' }}>
          <CardHeader label={displayLabel} fs={hdrFs} chip={MODE_STATE[active] || active} chipColor={activeColor} />
          <div style={{
            flex: 1, minHeight: 0, display: 'flex', flexDirection: side ? 'row' : 'column',
            alignItems: side ? 'center' : 'stretch', justifyContent: side ? 'space-between' : 'center', gap: side ? 6 : 2,
          }}>
            <span style={{ color: textColor, fontSize: curFs, fontWeight: 300, lineHeight: 1, letterSpacing: '-0.02em', whiteSpace: 'nowrap' }}>
              20.6°
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: Math.max(4, sb * 0.3), width: side ? 'auto' : '100%', justifyContent: 'space-between' }}>
                {stepBtn('−')}
                <span style={{ color: textColor, fontSize: tgtFs, fontWeight: 600, whiteSpace: 'nowrap' }}>22.5°</span>
                {stepBtn('+')}
              </div>
              <span style={{ color: CARD_GRAY, fontSize: clamp(tgtFs * 0.5, 7, 10), fontWeight: 600, letterSpacing: '0.08em' }}>TARGET</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 4, flexShrink: 0, height: pillH }}>
            {modes.map((md) => {
              const on = md === active;
              const mFmt = stateFormats[md] || {};
              return (
                <div key={md} style={{
                  flex: 1, minWidth: 0, borderRadius: pillH / 2,
                  background: on ? activeColor : 'rgba(255,255,255,0.07)',
                  color: on ? (mFmt.textColor || '#fff') : '#9aa0aa',
                  fontSize: pillFs, fontWeight: on ? 700 : 500, lineHeight: `${pillH}px`, textAlign: 'center',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textTransform: 'capitalize',
                }}>
                  {md === 'fan_only' ? 'fan' : md.replace('_', '/')}
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    // ---- camera ----------------------------------------------------------
    case 'camera': {
      const { m, pad } = cardMetrics(tileW, tileH);
      const ov = widget.overlay_button;
      const hasOverlay = ov?.entity_id || ov?.label;
      const iconSize = clamp(m * 0.28, 14, 40);
      const badgeFs = clamp(m * 0.075, 8, 11);
      const btn = clamp(m * 0.2, 18, 30);
      const src = widget.camera_source === 'url' ? widget.stream_url
        : widget.camera_source === 'entity' ? widget.camera_entity
        : widget.camera_entity || widget.stream_url;
      return (
        <div style={{
          position: 'absolute', inset: 0, overflow: 'hidden',
          background: 'radial-gradient(ellipse at 30% 25%, #3a4656 0%, #1d232c 55%, #0e1116 100%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
        }}>
          <Icon path={mdiCctv} size={iconSize} color="#fff" style={{ opacity: 0.22 }} />
          {src && m >= 90 && (
            <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 9, maxWidth: '80%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {src}
            </span>
          )}
          <div style={{
            position: 'absolute', top: pad, left: pad, display: 'flex', alignItems: 'center', gap: 4,
            background: 'rgba(0,0,0,0.55)', color: '#fff', fontSize: badgeFs, fontWeight: 700, letterSpacing: '0.06em',
            padding: `2px ${badgeFs * 0.7}px`, borderRadius: badgeFs,
          }}>
            <span style={{ width: badgeFs * 0.6, height: badgeFs * 0.6, borderRadius: '50%', background: '#ff453a' }} />
            LIVE
          </div>
          <div style={{
            position: 'absolute', top: pad, right: pad, width: btn, height: btn, borderRadius: '50%',
            background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}><Icon path={mdiRefresh} size={btn * 0.6} color="#fff" /></div>
          {hasOverlay && (
            <div style={{
              position: 'absolute', bottom: pad, right: pad, maxWidth: '60%',
              background: 'rgba(0,0,0,0.6)', color: '#fff', fontSize: clamp(m * 0.085, 9, 13), fontWeight: 600,
              padding: '3px 10px', borderRadius: 999, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {ov.label || 'Action'}
            </div>
          )}
        </div>
      );
    }

    // ---- 3D printer ------------------------------------------------------
    case 'printer':
    case 'printer3d': {
      const { m, pad, hdrFs, iw, ih } = cardMetrics(tileW, tileH);
      const visible = widget.visible_rows || ['nozzle', 'bed', 'time', 'progress', 'status', 'preview', 'layer'];
      const show = (r) => visible.includes(r);
      const STATS = {
        nozzle: { lbl: 'NOZZLE', val: widget.nozzle_target_entity ? '224/225°' : '224°' },
        bed:    { lbl: 'BED',    val: widget.bed_target_entity ? '60/60°' : '60°' },
        layer:  { lbl: 'LAYER',  val: widget.total_layers_entity ? '170/186' : '170', need: 'layer_entity' },
      };
      const stats = visible.filter((r) => STATS[r] && (!STATS[r].need || widget[STATS[r].need]));
      const hasThumb = show('preview') && widget.preview_entity && (widget.w ?? 1) >= 2;
      const gap = clamp(ih * 0.05, 3, 8);
      const statFs = clamp(Math.min(iw / Math.max(1, stats.length) / 4.8, m * 0.11), 8, 14);
      const statH = stats.length ? statFs * 2.3 : 0;
      const midH = ih - hdrFs * 1.45 - statH - gap * 2;
      const thumb = hasThumb ? Math.min(midH, iw * 0.4) : 0;
      const pctFs = format.textSize ? Number(format.textSize) : clamp(Math.min(midH * 0.45, (iw - thumb) * 0.3), 14, 56);
      const subFs = clamp(pctFs * 0.36, 8, 13);
      const unit = widget.progress_unit || '%';

      return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap, padding: pad, boxSizing: 'border-box', overflow: 'hidden' }}>
          <CardHeader label={displayLabel || '3D Printer'} fs={hdrFs} chip={show('status') ? 'Printing' : null} chipColor={ACCENT.green} />
          <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
            {hasThumb && (
              <div style={{
                width: thumb, height: thumb, flexShrink: 0, borderRadius: 8,
                background: 'linear-gradient(160deg, #3a414d, #23272f)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                opacity: 0.85,
              }}><Icon path={mdiPrinter3dNozzleOutline} size={thumb * 0.45} color="#9aa3b0" /></div>
            )}
            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: Math.max(2, gap * 0.6) }}>
              {show('progress') && (
                <>
                  <span style={{ color: textColor, fontSize: pctFs, fontWeight: 700, lineHeight: 1, letterSpacing: '-0.02em' }}>96{unit}</span>
                  <Bar pct={96} color={ACCENT.green} h={clamp(m * 0.035, 3, 6)} />
                </>
              )}
              {show('time') && (
                <span style={{ color: CARD_GRAY, fontSize: subFs, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {iw - thumb - (hasThumb ? 8 : 0) < subFs * 9 ? '37m left' : '37m left · ETA 21:07'}
                </span>
              )}
            </div>
          </div>
          {stats.length > 0 && (
            <div style={{ display: 'flex', height: statH, flexShrink: 0, borderTop: '0.5px solid rgba(255,255,255,0.08)', paddingTop: 2 }}>
              {stats.map((r) => (
                <div key={r} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <span style={{ color: CARD_GRAY, fontSize: Math.max(7, statFs * 0.68), fontWeight: 600, letterSpacing: '0.05em', lineHeight: 1.2 }}>{STATS[r].lbl}</span>
                  <span style={{ color: textColor, fontSize: statFs, fontWeight: 600, lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{STATS[r].val}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    // ---- countdown timer -------------------------------------------------
    case 'timer': {
      const { m, pad, hdrFs, iw, ih } = cardMetrics(tileW, tileH);
      const secs = widget.default_seconds || 300;
      const h = Math.floor(secs / 3600);
      const mm = String(Math.floor((secs % 3600) / 60)).padStart(2, '0');
      const ss = String(secs % 60).padStart(2, '0');
      const timeStr = h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
      const timerFs = format.textSize ? Number(format.textSize)
        : clamp(Math.min(ih * 0.42, iw / (timeStr.length * 0.62)), 16, 80);
      const hintFs = clamp(m * 0.075, 8, 11);
      return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: 4, padding: pad, boxSizing: 'border-box', overflow: 'hidden' }}>
          <CardHeader label={displayLabel || 'Timer'} fs={hdrFs} />
          <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: textColor, fontSize: timerFs, fontWeight: 600, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
              {timeStr}
            </span>
          </div>
          <span style={{ color: 'rgba(255,255,255,0.28)', fontSize: hintFs, textAlign: 'center', whiteSpace: 'pre', flexShrink: 0 }}>
            {widget.configurable === false ? 'tap · start' : 'tap · start   hold · set'}
          </span>
          <Bar pct={100} color={ACCENT.blue} h={clamp(m * 0.025, 2, 4)} />
        </div>
      );
    }

    // ---- embedded webpage ------------------------------------------------
    case 'webpage': {
      const url = widget.stream_url;
      const shortUrl = url
        ? (url.length > 26 ? url.slice(0, 24) + '…' : url)
        : 'no URL configured';
      const iconFs = Math.max(14, Math.min(24, IH * 0.22));
      return (
        <div style={colStyle}>
          {widget.label && <TitleLabel text={widget.label} />}
          <div style={{
            flex: 1, minHeight: 0, background: '#111', borderRadius: 3,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 4,
          }}>
            <Icon path={mdiWeb} size={iconFs} color="#fff" style={{ opacity: 0.2 }} />
            <span style={{ color: '#555', fontSize: '9px', textAlign: 'center', padding: '0 4px' }}>{shortUrl}</span>
          </div>
        </div>
      );
    }

    // ---- Mealie recipe browser / fixed recipe ----------------------------
    case 'mealie': {
      const { pad, hdrFs, iw, ih } = cardMetrics(tileW, tileH);
      const slug = (widget.recipe_slug || '').trim();
      const hdrGap = clamp(ih * 0.04, 4, 8);
      const bodyH = ih - hdrFs * 1.45 - hdrGap;
      const title = slug
        ? slug.split(/[-_]+/).filter(Boolean).map((p) => p[0].toUpperCase() + p.slice(1)).join(' ')
        : (widget.label || 'Recipes');
      const headerRight = (
        <>
          {!slug && <span style={{ color: TEXT_DIM, fontSize: Math.max(8, hdrFs - 1), whiteSpace: 'nowrap', flexShrink: 0 }}>24 recipes</span>}
          <Icon path={mdiRefresh} size={hdrFs * 1.3} color={CARD_GRAY} />
        </>
      );

      let body;
      if (slug) {
        // Fixed recipe: ingredients (tap-to-check) then numbered steps.
        const section = widget.visible_section || 'both';
        const fs = 15;
        const box = Math.ceil(fs * 1.2);
        const badge = Math.ceil(fs * 1.55);
        const secHdr = (t) => (
          <div style={{ color: TEXT_DIM, fontSize: 12, fontWeight: 500, letterSpacing: '0.06em', lineHeight: '16px', marginBottom: 8 }}>{t}</div>
        );
        body = (
          <>
            {section !== 'steps' && (
              <>
                {secHdr(`INGREDIENTS · ${MEALIE_INGREDIENTS.length}`)}
                {MEALIE_INGREDIENTS.map((t, i) => {
                  const on = i === 0;
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '6px 8px 6px 4px', marginBottom: 2 }}>
                      <span style={{
                        width: box, height: box, borderRadius: '50%', boxSizing: 'border-box', flexShrink: 0,
                        border: `2px solid ${on ? COOK_GREEN : TEXT_DIM}`, background: on ? COOK_GREEN : 'transparent',
                        marginTop: (fs * 1.25 - box) / 2, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: '#1a1c20', fontSize: box * 0.6, fontWeight: 800, lineHeight: 1,
                      }}>{on ? <Icon path={mdiCheck} size={box * 0.75} color="#1a1c20" /> : null}</span>
                      <span style={{ color: on ? TEXT_DIM : textColor, fontSize: fs, lineHeight: 1.25, minWidth: 0 }}>{t}</span>
                    </div>
                  );
                })}
              </>
            )}
            {section !== 'ingredients' && (
              <div style={{ marginTop: section === 'steps' ? 0 : 18 }}>
                {secHdr(`STEPS · ${MEALIE_STEPS.length}`)}
                {MEALIE_STEPS.map((t, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '7px 8px 7px 4px', marginBottom: 4 }}>
                    <span style={{
                      width: badge, height: badge, borderRadius: '50%', background: CARD_HI, flexShrink: 0,
                      color: textColor, fontSize: fs * 0.8, fontWeight: 500, lineHeight: `${badge}px`, textAlign: 'center',
                    }}>{i + 1}</span>
                    <span style={{ color: textColor, fontSize: fs, lineHeight: 1.25, minWidth: 0, paddingTop: (badge - fs * 1.25) / 2 }}>{t}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        );
      } else {
        // Recipe grid: column count follows the iPad card's breakpoints.
        const cols = iw > 560 ? 3 : iw > 250 ? 2 : 1;
        const nameFs = Math.min(22, Number(format.textSize) || 16);
        const rows = Math.ceil(bodyH / (56 + 8)) + 1;
        const recipes = Array.from({ length: rows * cols }, (_, i) => MEALIE_SAMPLES[i % MEALIE_SAMPLES.length]);
        body = (
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: 8 }}>
            {recipes.map((r, i) => (
              <div key={i} style={{ background: CARD_HI, borderRadius: 10, padding: 12, minHeight: 56, boxSizing: 'border-box', minWidth: 0 }}>
                <div style={{ color: textColor, fontSize: nameFs, fontWeight: 500, lineHeight: 1.2, ...lineClamp(3) }}>{r.name}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 8, maxHeight: 45, overflow: 'hidden' }}>
                  {r.tags.map((t) => {
                    const c = mealieTagColor(t);
                    return (
                      <span key={t} style={{
                        height: 20, lineHeight: '20px', padding: '0 9px', borderRadius: 10, boxSizing: 'border-box',
                        color: c, background: tint(c, 18), fontSize: 11, fontWeight: 500,
                        maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>{t}</span>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        );
      }

      return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: hdrGap, padding: pad, boxSizing: 'border-box', overflow: 'hidden' }}>
          <CardHeader label={title} fs={hdrFs} right={headerRight} />
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>{body}</div>
        </div>
      );
    }

    // ---- sous vide cooker (previewed while cooking) ----------------------
    case 'sousvide': {
      const { m, pad, hdrFs, ih } = cardMetrics(tileW, tileH);
      const fahr = /F/i.test(widget.unit || '°C');
      const gap = clamp(ih * 0.03, 2, 6);
      const tgtFs = clamp(m * 0.1, 9, 13);
      const timeFs = clamp(m * 0.09, 8, 12);
      const avail = ih - hdrFs * 1.45 - tgtFs * 1.3 - timeFs * 1.3 - gap * 3;
      const curFs = Math.max(12, Math.min(Number(format.textSize) || 40, 46, avail * 0.9));
      const sub = { color: CARD_GRAY, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flexShrink: 0, lineHeight: 1.3 };
      return (
        <div style={{
          position: 'absolute', inset: 0, background: tint(COOK_GREEN, 10),
          display: 'flex', flexDirection: 'column', gap, padding: pad, boxSizing: 'border-box', overflow: 'hidden',
        }}>
          <CardHeader label={widget.label || 'Sous Vide'} fs={hdrFs} chip="Cooking" chipColor={COOK_GREEN} chipBgPct={18} />
          <span style={{ color: textColor, fontSize: curFs, fontWeight: 300, lineHeight: 1.1, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', flexShrink: 0 }}>
            {fahr ? '133.2°' : '56.2°'}
          </span>
          <span style={{ ...sub, fontSize: tgtFs }}>Target {fahr ? '135°' : '57°'}</span>
          <div style={{ flex: 1, minHeight: 0 }} />
          <span style={{ ...sub, fontSize: timeFs }}>1h 12m left · done ~21:07</span>
        </div>
      );
    }

    // ---- appliance (washer, dryer, etc.) ---------------------------------
    case 'appliance': {
      const { m, pad, hdrFs, iw, ih } = cardMetrics(tileW, tileH);
      const gap = clamp(ih * 0.04, 2, 7);
      const progFs = clamp(m * 0.1, 9, 15);
      const bigFs = format.textSize ? Number(format.textSize) : clamp(Math.min(ih * 0.3, iw * 0.3), 16, 60);
      const subFs = clamp(m * 0.085, 8, 12);
      return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap, padding: pad, boxSizing: 'border-box', overflow: 'hidden' }}>
          <CardHeader label={displayLabel} fs={hdrFs} chip="Running" chipColor={ACCENT.blue} />
          <span style={{ color: '#c9cdd4', fontSize: progFs, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flexShrink: 0 }}>
            Cotton 40°<span style={{ color: CARD_GRAY }}> · Rinse</span>
          </span>
          <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center' }}>
            <span style={{ color: textColor, fontSize: bigFs, fontWeight: 700, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>1:12</span>
          </div>
          <Bar pct={58} color={ACCENT.blue} h={clamp(m * 0.035, 3, 6)} />
          <span style={{ color: CARD_GRAY, fontSize: subFs, flexShrink: 0 }}>Done ~21:07</span>
        </div>
      );
    }

    // ---- media player ----------------------------------------------------
    case 'mediaplayer':
      return <MediaPreview widget={widget} W={tileW} H={tileH} />;

    // ---- cover (blinds / shades / garage) --------------------------------
    case 'cover': {
      // Ordered granular items (cover_items). Fall back to expanding legacy
      // cover_controls groups, else a representative auto-detect hint.
      const expandGroups = (groups) => {
        const o = [];
        for (const g of groups || []) {
          if (g === 'buttons') o.push('open', 'stop', 'close');
          else if (g === 'slider') o.push('position');
          else if (g === 'presets') o.push('presets');
          else if (g === 'tilt') o.push('tilt_open', 'tilt_close', 'tilt_slider');
        }
        return o;
      };
      const items = (Array.isArray(widget.cover_items) && widget.cover_items.length) ? widget.cover_items
        : (Array.isArray(widget.cover_controls) && widget.cover_controls.length) ? expandGroups(widget.cover_controls)
        : ['open', 'stop', 'close', 'position'];
      const layoutMode = widget.cover_layout || 'auto';
      const horiz = layoutMode === 'horizontal' ? true : layoutMode === 'vertical' ? false : (tileW >= tileH);
      const presets = (Array.isArray(widget.position_presets) && widget.position_presets.length)
        ? widget.position_presets : [0, 25, 75, 100];

      const titleH = widget.label ? 16 : 0;
      const statusH = Math.max(20, Math.min((IH - titleH) * 0.28, 50));
      const BTN = { open: '▲', close: '▼', stop: '■' };
      const isBtn = (t) => t in BTN || t === 'tilt_open' || t === 'tilt_close';

      const Slat = ({ open }) => (
        <svg width="20" height="16" viewBox="0 0 20 16" style={{ display: 'block' }}>
          {[4, 8, 12].map((y, i) => (
            <line key={i} x1="3" y1={y + (open ? 2 : -2)} x2="17" y2={y + (open ? -2 : 2)}
              stroke="#cfcfcf" strokeWidth="1.6" strokeLinecap="round" />
          ))}
        </svg>
      );
      const Pill = ({ children, extra }) => (
        <div style={{ background: 'rgba(255,255,255,0.10)', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#cfcfcf', fontWeight: 'bold', ...extra }}>{children}</div>
      );
      const btnContent = (t) => t === 'tilt_open' ? <Slat open /> : t === 'tilt_close' ? <Slat /> : BTN[t];
      const VBar = ({ pct = 60 }) => (
        <div style={{ width: 6, height: '100%', background: 'rgba(255,255,255,0.12)', borderRadius: 4, position: 'relative' }}>
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: `${pct}%`, background: 'rgba(255,255,255,0.45)', borderRadius: 4 }} />
        </div>
      );
      const presetRow = (key) => (
        <div key={key} style={{ display: 'flex', gap: 3, flexShrink: 0, height: 20 }}>
          {presets.slice(0, 6).map((p, i) => (
            <Pill key={i} extra={{ flex: 1, fontSize: 9, fontWeight: 'normal', borderRadius: 10, color: '#bbb' }}>{p}%</Pill>
          ))}
        </div>
      );

      // Build horizontal rows: consecutive buttons merge; sliders/presets own rows.
      const rows = [];
      let acc = [];
      const flush = () => { if (acc.length) { rows.push({ kind: 'buttons', toks: acc }); acc = []; } };
      for (const t of items) {
        if (isBtn(t)) { acc.push(t); continue; }
        flush();
        if (t === 'position' || t === 'tilt_slider') rows.push({ kind: 'slider', tilt: t === 'tilt_slider' });
        else if (t === 'presets') rows.push({ kind: 'presets' });
      }
      flush();

      const sliderToks = items.filter((t) => t === 'position' || t === 'tilt_slider');
      const btnToks = items.filter(isBtn);
      const hasPresets = items.includes('presets');

      return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', padding: '4px 6px', boxSizing: 'border-box', gap: 4 }}>
          {widget.label && <TitleLabel text={widget.label} />}
          <div style={{ height: statusH, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: textColor, fontSize: Math.max(13, Math.min(20, statusH * 0.5)), fontWeight: 'bold' }}>CLOSED&nbsp;0%</span>
          </div>
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {horiz ? (
              rows.map((row, i) => {
                if (row.kind === 'presets') return presetRow(i);
                if (row.kind === 'slider') return (
                  <div key={i} style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                    <div style={{ width: '100%', height: 5, background: 'rgba(255,255,255,0.12)', borderRadius: 4 }}>
                      <div style={{ width: row.tilt ? '40%' : '60%', height: '100%', background: 'rgba(255,255,255,0.45)', borderRadius: 4 }} />
                    </div>
                  </div>
                );
                return (
                  <div key={i} style={{ flex: 1, display: 'flex', gap: 4 }}>
                    {row.toks.map((t, j) => <Pill key={j} extra={{ flex: 1, fontSize: 14 }}>{btnContent(t)}</Pill>)}
                  </div>
                );
              })
            ) : (
              <>
                <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 5 }}>
                  {sliderToks.map((t, i) => (
                    <div key={i} style={{ width: 18, display: 'flex', justifyContent: 'center' }}><VBar pct={t === 'tilt_slider' ? 40 : 60} /></div>
                  ))}
                  {btnToks.length > 0 && (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {btnToks.map((t, i) => <Pill key={i} extra={{ flex: 1, fontSize: 14 }}>{btnContent(t)}</Pill>)}
                    </div>
                  )}
                </div>
                {hasPresets && presetRow('presets')}
              </>
            )}
          </div>
        </div>
      );
    }

    // ---- fallback --------------------------------------------------------
    default: {
      const def = findType(type);
      return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4px 6px', boxSizing: 'border-box' }}>
          {def && <Icon path={def.icon} size={Math.min(22, IH * 0.3)} color={textColor} />}
          <span style={{ color: textColor, fontSize: '12px', marginTop: 2, textAlign: 'center' }}>{displayLabel}</span>
        </div>
      );
    }
  }
}

// Media player: same layout rules as the app (DashboardViewController+Media.m),
// shown with a player that supports everything (output, volume, shuffle, repeat).
function MediaPreview({ widget, W, H }) {
  const clampN = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const pad = Math.min(W, H) < 125 ? 9 : 11;
  const showArt = widget.show_art !== false;
  let info = { x: pad, y: pad, w: W - pad * 2, h: H - pad * 2 };
  let art = null, backdrop = false;
  if (showArt) {
    const sideS = Math.floor(Math.min(H - pad * 2, W * 0.55));
    const sideInfoW = W - pad * 3 - sideS;
    const stackH = Math.floor(Math.min(W - pad * 2, H - pad * 3 - Math.max(96, H * 0.44)));
    if (W >= H * 1.1 && sideS >= 84 && sideInfoW >= 150 && sideS >= (H - pad * 2) * 0.8) {
      art = { x: pad, y: pad, w: sideS, h: sideS };
      info = { x: pad * 2 + sideS, y: pad, w: sideInfoW, h: H - pad * 2 };
    } else if (W >= 120 && stackH >= 72) {
      art = { x: pad, y: pad, w: W - pad * 2, h: stackH };
      info = { x: pad, y: pad * 2 + stackH, w: W - pad * 2, h: H - pad * 3 - stackH };
    } else backdrop = true;
  }
  const anchored = backdrop || !showArt;
  const R = info, iw = R.w, ih = R.h, gap = 6;
  const b0 = clampN(iw / 5.2, 30, 64), fs0 = clampN(iw / 12.5, 13, 28);
  let header = false, progress = false, volume = false, lines = 1, k = 1;
  const total = (kk) => {
    const fs = Math.max(13, fs0 * kk), b = Math.max(30, b0 * kk);
    let t = Math.ceil(fs * 1.22) * lines + Math.ceil(fs * 0.74 * 1.3) + b, n = 2;
    if (header) { t += Math.ceil(clampN(fs * 0.62, 12, 17) * 1.9); n++; }
    if (progress) { t += 32; n++; }
    if (volume) { t += Math.max(30, b * 0.6); n++; }
    return t + gap * (n - 1);
  };
  k = 0.8;
  while (total(k) > ih && k > 0.62) k -= 0.04;
  if (ih - total(k) >= 34) progress = true;
  if (ih - total(k) >= 34) volume = true;
  if (iw >= 200 && ih - total(k) >= 28) header = true;
  if (ih - total(k) >= fs0 * k * 1.4 && iw >= 180) lines = 2;
  const bMax = Math.min(76, iw >= 96 ? (iw - 12) / 2.44 : 76);
  while (k < 1.7 && b0 * (k + 0.04) <= bMax && fs0 * (k + 0.04) <= 34 && total(k + 0.04) <= ih) k += 0.04;
  const fs = Math.floor(Math.max(13, fs0 * k)), b = Math.floor(Math.max(30, b0 * k)), sb = Math.floor(b * 0.72);
  const blocks = 2 + header + progress + volume;
  const spare = Math.max(0, ih - total(k));
  const between = anchored ? 0 : Math.min(spare / (blocks + 1), 30);
  let y = R.y + (anchored ? 0 : Math.floor((spare - between * (blocks - 1)) / 2));
  const els = [];
  const hf = clampN(fs * 0.62, 12, 17), hh = Math.ceil(hf * 1.9);
  if (header) {
    const outW = Math.min(iw * 0.55, 220);
    els.push(<div key="h" style={{ position: 'absolute', left: R.x, top: y, width: iw - outW - 8, height: hh, lineHeight: `${hh}px`, fontSize: hf, color: '#9aa3af', fontWeight: 500, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{widget.label || 'Media'} · Spotify</div>);
    els.push(<div key="o" style={{ position: 'absolute', left: R.x + iw - outW, top: y, width: outW, height: hh, borderRadius: hh / 2, background: 'rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', gap: 4, paddingLeft: 8, boxSizing: 'border-box', color: '#f2f4f7', fontSize: hf, fontWeight: 500, overflow: 'hidden', whiteSpace: 'nowrap' }}><Icon path={mdiSpeaker} size={hh * 0.62} color="#f2f4f7" />Kitchen</div>);
    y += hh + gap + between;
  } else if (iw >= 120) {
    els.push(<div key="oi" style={{ position: 'absolute', left: R.x + iw - 28, top: y - 2, width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon path={mdiSpeaker} size={14} color="#f2f4f7" /></div>);
  }
  const textW = header || iw < 120 ? iw : iw - 34;
  const tH = Math.ceil(fs * 1.22) * lines, af = Math.max(12, Math.floor(fs * 0.74));
  els.push(<div key="t" style={{ position: 'absolute', left: R.x, top: y, width: textW, height: tH, fontSize: fs, lineHeight: `${Math.ceil(fs * 1.22)}px`, color: '#f2f4f7', fontWeight: 500, overflow: 'hidden', ...(lines === 1 ? { whiteSpace: 'nowrap', textOverflow: 'ellipsis' } : {}) }}>Bohemian Rhapsody - Remastered 2011</div>);
  y += tH;
  els.push(<div key="a" style={{ position: 'absolute', left: R.x, top: y, width: textW, fontSize: af, color: '#9aa3af', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Queen</div>);
  y += Math.ceil(af * 1.3) + gap + between;
  const rest = (progress ? 32 + gap + between : 0) + b + (volume ? Math.max(30, b * 0.6) + gap + between : 0);
  if (anchored) y = R.y + ih - rest;
  if (progress) {
    els.push(<div key="p" style={{ position: 'absolute', left: R.x, top: y + 7, width: iw, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.16)' }}><div style={{ width: '35%', height: '100%', borderRadius: 2, background: '#f2f4f7' }} /></div>);
    els.push(<div key="pt" style={{ position: 'absolute', left: R.x, top: y + 19, width: iw, display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#9aa3af', fontVariantNumeric: 'tabular-nums' }}><span>1:12</span><span>5:55</span></div>);
    y += 32 + gap + between;
  }
  const pn = iw >= b + sb * 2 + 12, extra = iw >= b + sb * 4 + 40;
  const row = [...(extra ? ['shuffle'] : []), ...(pn ? ['prev'] : []), 'play', ...(pn ? ['next'] : []), ...(extra ? ['repeat'] : [])];
  const used = row.reduce((n, r) => n + (r === 'play' ? b : sb), 0);
  const sp = row.length > 1 ? Math.min(Math.max(4, (iw - used) / (row.length - 1)), Math.max(14, b * 0.55)) : 0;
  let x = R.x + Math.floor((iw - used - sp * (row.length - 1)) / 2);
  for (const r of row) {
    const sz = r === 'play' ? b : sb;
    const top = y + Math.floor((b - sz) / 2);
    const icon = r === 'shuffle' ? <Icon path={mdiShuffleVariant} size={sz * 0.5} color="#f2f4f7" style={{ opacity: 0.45 }} />
      : r === 'repeat' ? <Icon path={mdiRepeat} size={sz * 0.5} color="#f2f4f7" style={{ opacity: 0.45 }} />
      : <TransportIcon type={r} size={sz * 0.5} color={r === 'play' ? '#1a1c20' : undefined} />;
    els.push(<div key={r} style={{ position: 'absolute', left: x, top, width: sz, height: sz, borderRadius: '50%', background: r === 'play' ? '#f2f4f7' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{icon}</div>);
    x += sz + sp;
  }
  y += b + gap + between;
  if (volume) {
    const vh = Math.max(30, b * 0.6), vs = Math.min(vh, 34);
    els.push(<div key="vi" style={{ position: 'absolute', left: R.x - 4, top: y + (vh - vs) / 2, width: vs, height: vs, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon path={mdiVolumeHigh} size={vs * 0.5} color="#f2f4f7" /></div>);
    els.push(<div key="v" style={{ position: 'absolute', left: R.x + vs + 2, top: y + vh / 2 - 2, width: iw - vs - 2, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.16)' }}><div style={{ width: '60%', height: '100%', borderRadius: 2, background: '#f2f4f7' }} /></div>);
  }
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', fontFamily: '-apple-system, Helvetica Neue, sans-serif' }}>
      {backdrop && <><div style={{ position: 'absolute', inset: 0, background: ART_BG }} /><div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.58)' }} /></>}
      {art && (
        <div style={{ position: 'absolute', left: art.x, top: art.y, width: art.w, height: art.h, borderRadius: 10, background: ART_BG, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon path={mdiMusicNote} size={Math.min(art.w, art.h) * 0.36} color="rgba(255,255,255,0.6)" />
        </div>
      )}
      {els}
      {!progress && <div style={{ position: 'absolute', left: 12, right: 12, bottom: 0, height: 3, borderRadius: 1.5, background: 'rgba(255,255,255,0.12)' }}><div style={{ width: '35%', height: '100%', background: '#f2f4f7', borderRadius: 1.5 }} /></div>}
    </div>
  );
}
