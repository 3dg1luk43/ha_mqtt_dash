// Settings specific to each card type (the shared label / entity / appearance /
// position fields live in WidgetSettings).
import { mdiArrowUp, mdiArrowDown, mdiClose, mdiPlus } from '@mdi/js';
import EntityPicker from './EntityPicker';
import { Field, TextInput, NumberInput, Toggle, Segmented, ColorField, Icon, IconButton } from '../ui';

export default function CardFields({ widget, onChange }) {
  const F = FIELDS[widget.type];
  return F ? <F widget={widget} onChange={onChange} /> : null;
}

const FIELDS = {
  light: LightFields,
  sensor: SensorFields, value: SensorFields, person: SensorFields,
  label: LabelFields,
  clock: ClockFields,
  weather: WeatherFields,
  climate: ClimateFields,
  camera: CameraFields,
  printer: PrinterFields,
  timer: TimerFields,
  webpage: WebpageFields,
  mealie: MealieFields,
  sousvide: SousvideFields,
  appliance: ApplianceFields,
  mediaplayer: MediaPlayerFields,
  video: VideoFields,
  cover: CoverFields,
};

function LightFields({ widget, onChange }) {
  return (
    <Toggle label="Dimmable" checked={widget.dimmable !== false}
      hint={widget.dimmable !== false ? 'Drag across the card to dim, if the light supports brightness' : 'On / off only'}
      onChange={(v) => onChange({ dimmable: v ? undefined : false })} />
  );
}

function SensorFields({ widget, onChange }) {
  return (
    <>
      <Field label="Unit" hint="Leave empty to use the entity's unit">
        <TextInput value={widget.unit} onChange={(v) => onChange({ unit: v || undefined })} placeholder="°C, %, W" />
      </Field>
      <Field label="Preview value" hint="Only shown here in the editor">
        <TextInput value={widget.preview_value} onChange={(v) => onChange({ preview_value: v || undefined })} placeholder="42" />
      </Field>
    </>
  );
}

function LabelFields({ widget, onChange }) {
  return (
    <Field label="Text">
      <textarea className="ed-input" rows={3} value={widget.text ?? ''} onChange={(e) => onChange({ text: e.target.value })} />
    </Field>
  );
}

function ClockFields({ widget, onChange }) {
  return (
    <Field label="Format" hint="HH hour (24 h), hh hour (12 h), MM minutes, SS seconds, DD day, Mo month, YY year">
      <TextInput mono value={widget.time_pattern} onChange={(v) => onChange({ time_pattern: v || undefined })} placeholder="HH:MM" />
    </Field>
  );
}

const WEATHER_ATTRS = [
  ['temperature', 'Temperature'], ['humidity', 'Humidity'], ['wind_speed', 'Wind speed'], ['pressure', 'Pressure'],
  ['visibility', 'Visibility'], ['dew_point', 'Dew point'], ['cloud_coverage', 'Cloud coverage'], ['uv_index', 'UV index'],
  ['precipitation', 'Precipitation'],
];

function WeatherFields({ widget, onChange }) {
  const attrs = widget.attrs ?? [];
  const units = widget.attr_units ?? {};
  return (
    <Field label="Show">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {WEATHER_ATTRS.map(([key, label]) => (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <Toggle label={label} checked={attrs.includes(key)}
                onChange={(on) => onChange({ attrs: on ? [...attrs, key] : attrs.filter((a) => a !== key) })} />
            </div>
            {attrs.includes(key) && (
              <input className="ed-input" style={{ width: 64 }} value={units[key] ?? ''} placeholder="unit" aria-label={`${label} unit`}
                onChange={(e) => onChange({ attr_units: { ...units, [key]: e.target.value } })} />
            )}
          </div>
        ))}
      </div>
    </Field>
  );
}

const CLIMATE_MODES = [['off', 'Off'], ['heat', 'Heat'], ['cool', 'Cool'], ['auto', 'Auto'], ['heat_cool', 'Heat/cool'], ['fan_only', 'Fan'], ['dry', 'Dry']];

function ClimateFields({ widget, onChange }) {
  const modes = widget.modes ?? [];
  const formats = widget.state_formats ?? {};
  return (
    <>
      <Field label="Temperature step" hint="Empty: taken from the entity">
        <NumberInput allowEmpty min={0.1} step={0.1} value={widget.temp_step} placeholder="auto"
          onChange={(v) => onChange({ temp_step: v > 0 ? v : undefined })} />
      </Field>
      <Field label="Mode buttons" hint="None selected: the entity's own modes">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {CLIMATE_MODES.map(([m, label]) => (
            <div key={m}>
              <Toggle label={label} checked={modes.includes(m)}
                onChange={(on) => onChange({ modes: on ? [...modes, m] : modes.filter((x) => x !== m) })} />
              {modes.includes(m) && (
                <div style={{ marginTop: 6 }}>
                  <ColorField label={`${label} color`} value={formats[m]?.bgColor}
                    onChange={(c) => onChange({ state_formats: { ...formats, [m]: { ...(formats[m] ?? {}), bgColor: c } } })} />
                </div>
              )}
            </div>
          ))}
        </div>
      </Field>
    </>
  );
}

function CameraFields({ widget, onChange }) {
  const overlay = widget.overlay_button ?? {};
  const setOverlay = (k, v) => onChange({ overlay_button: { ...overlay, [k]: v } });
  // camera_source is editor-only (not exported); derive it for imported profiles
  const source = widget.camera_source ?? (widget.camera_entity ? 'entity' : widget.stream_url ? 'url' : 'entity');
  return (
    <>
      <Field label="Source">
        <Segmented value={source} onChange={(v) => onChange({ camera_source: v })} options={[
          { value: 'entity', label: 'Camera entity' }, { value: 'url', label: 'Stream URL' },
        ]} />
      </Field>
      {source === 'entity' ? (
        <Field label="Camera" hint="Home Assistant fetches the frames and relays them, so any camera HA can show works">
          <EntityPicker domains={['camera']} value={widget.camera_entity} onChange={(v) => onChange({ camera_entity: v })} />
        </Field>
      ) : (
        <Field label="Stream URL" hint="Plain-HTTP MJPEG stream or JPEG snapshot; the iPad can't play RTSP, HLS or WebRTC">
          <TextInput mono value={widget.stream_url} onChange={(v) => onChange({ stream_url: v })} placeholder="http://192.168.1.50/mjpeg" />
        </Field>
      )}
      <div className="ed-row">
        <Field label="Refresh (s)">
          <NumberInput allowEmpty min={0.1} step={0.5} value={widget.refresh_interval} placeholder="1"
            onChange={(v) => onChange({ refresh_interval: v > 0 ? v : undefined })} />
        </Field>
        <Field label="Picture">
          <Segmented value={widget.scale_mode ?? 'fit'} onChange={(v) => onChange({ scale_mode: v })} options={[
            { value: 'fit', label: 'Fit' }, { value: 'stretch', label: 'Fill' },
          ]} />
        </Field>
      </div>
      <Field label="Button on the picture" hint="Optional, e.g. to switch a light next to the camera">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <TextInput value={overlay.label} onChange={(v) => setOverlay('label', v)} placeholder="Button text" />
          <EntityPicker value={overlay.entity_id} onChange={(v) => setOverlay('entity_id', v)} />
          <Segmented value={overlay.action ?? 'toggle'} onChange={(v) => setOverlay('action', v)} options={[
            { value: 'toggle', label: 'Toggle' }, { value: 'turn_on', label: 'Turn on' }, { value: 'turn_off', label: 'Turn off' },
          ]} />
        </div>
      </Field>
    </>
  );
}

const PRINTER_ENTITIES = [
  ['status_entity', 'Status'], ['progress_entity', 'Progress'], ['time_entity', 'Time left'],
  ['nozzle_entity', 'Nozzle temperature'], ['nozzle_target_entity', 'Nozzle target', true],
  ['bed_entity', 'Bed temperature'], ['bed_target_entity', 'Bed target', true],
  ['preview_entity', 'Preview image', true, ['image', 'camera']],
  ['layer_entity', 'Current layer', true], ['total_layers_entity', 'Total layers', true],
];
const PRINTER_ROWS = { status: 'Status', progress: 'Progress', time: 'Time left', nozzle: 'Nozzle', bed: 'Bed', preview: 'Preview', layer: 'Layer' };

function PrinterFields({ widget, onChange }) {
  return (
    <>
      {PRINTER_ENTITIES.map(([key, label, optional, domains]) => (
        <Field key={key} label={optional ? `${label} (optional)` : label}>
          <EntityPicker domains={domains ?? ['sensor']} value={widget[key]} onChange={(v) => onChange({ [key]: v })} />
        </Field>
      ))}
      <Field label="Rows, in order">
        <OrderedList labels={PRINTER_ROWS} items={widget.visible_rows ?? Object.keys(PRINTER_ROWS)}
          onChange={(rows) => onChange({ visible_rows: rows })} />
      </Field>
    </>
  );
}

const TIMER_QUICK = [[60, '1 min'], [180, '3 min'], [300, '5 min'], [600, '10 min'], [900, '15 min'], [1800, '30 min']];
const fmtMinutes = (s) => String(Math.round((s / 60) * 100) / 100);

function TimerFields({ widget, onChange }) {
  const secs = widget.default_seconds ?? 300;
  const presets = Array.isArray(widget.presets) ? widget.presets : [];
  return (
    <>
      <Field label="Starts at" hint={`${Math.floor(secs / 60)} min ${secs % 60 ? `${secs % 60} s` : ''}`.trim()}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
          <NumberInput min={1} value={secs} onChange={(v) => onChange({ default_seconds: Math.max(1, Math.round(v)) })} />
          <span className="ed-hint">seconds</span>
        </div>
      </Field>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {TIMER_QUICK.map(([v, label]) => (
          <button key={v} type="button" className={`ed-btn ${secs === v ? 'ed-btn--filled' : 'ed-btn--outlined'}`} style={{ height: 30, padding: '0 10px', fontSize: 13 }}
            onClick={() => onChange({ default_seconds: v })}>{label}</button>
        ))}
      </div>
      <Field label="Quick picks (minutes)" hint="Comma separated; empty uses the app's defaults. Times set on the panel can be saved there too.">
        <input key={widget.id} className="ed-input" defaultValue={presets.map(fmtMinutes).join(', ')} placeholder="1, 3, 5, 10"
          onBlur={(e) => {
            const vals = e.target.value.split(',').map((t) => parseFloat(t.trim())).filter((m) => Number.isFinite(m) && m > 0).map((m) => Math.max(1, Math.round(m * 60)));
            onChange({ presets: vals.length ? vals : undefined });
          }} />
      </Field>
      <Toggle label="Duration can be changed on the panel" checked={widget.configurable !== false}
        onChange={(v) => onChange({ configurable: v ? undefined : false })} />
    </>
  );
}

function WebpageFields({ widget, onChange }) {
  return (
    <Field label="Address" hint="Self-signed HTTPS certificates are accepted">
      <TextInput mono value={widget.stream_url} onChange={(v) => onChange({ stream_url: v })} placeholder="http://192.168.1.100/page" />
    </Field>
  );
}

function MealieFields({ widget, onChange }) {
  return (
    <>
      <Field label="Mealie address">
        <TextInput mono value={widget.mealie_url} onChange={(v) => onChange({ mealie_url: v })} placeholder="http://192.168.1.100:9000" />
      </Field>
      <Field label="API token" hint="Mealie: profile → API tokens">
        <TextInput type="password" value={widget.mealie_api_key} onChange={(v) => onChange({ mealie_api_key: v })} autoComplete="off" />
      </Field>
      <Field label="Recipe" hint="Optional: the slug of one recipe to show. Empty shows the recipe list.">
        <TextInput mono value={widget.recipe_slug} onChange={(v) => onChange({ recipe_slug: v || undefined })} placeholder="pasta-carbonara" />
      </Field>
      <Field label="Show">
        <Segmented value={widget.visible_section ?? 'both'} onChange={(v) => onChange({ visible_section: v })} options={[
          { value: 'both', label: 'Both' }, { value: 'ingredients', label: 'Ingredients' }, { value: 'steps', label: 'Steps' },
        ]} />
      </Field>
    </>
  );
}

function SousvideFields({ widget, onChange }) {
  return (
    <>
      <Field label="Water temperature"><EntityPicker domains={['sensor']} value={widget.temp_entity} onChange={(v) => onChange({ temp_entity: v })} /></Field>
      <Field label="Target temperature"><EntityPicker domains={['sensor', 'number', 'climate']} value={widget.target_entity} onChange={(v) => onChange({ target_entity: v })} /></Field>
      <Field label="Time left" hint="Minutes, shown as h:mm"><EntityPicker domains={['sensor']} value={widget.time_entity} onChange={(v) => onChange({ time_entity: v })} /></Field>
      <Field label="Unit"><TextInput value={widget.unit} onChange={(v) => onChange({ unit: v || undefined })} placeholder="°C" /></Field>
    </>
  );
}

function ApplianceFields({ widget, onChange }) {
  return (
    <>
      <Field label="Program"><EntityPicker domains={['sensor', 'select']} value={widget.program_entity} onChange={(v) => onChange({ program_entity: v })} /></Field>
      <Field label="Time left" hint="Minutes, shown as h:mm"><EntityPicker domains={['sensor']} value={widget.time_entity} onChange={(v) => onChange({ time_entity: v })} /></Field>
      <Field label="Progress (optional)" hint="0–100 %. Empty: found next to the time-left sensor (…_progress)">
        <EntityPicker domains={['sensor']} value={widget.progress_entity} onChange={(v) => onChange({ progress_entity: v })} />
      </Field>
      <Field label="Phase (optional)" hint="Empty: found next to the time-left sensor (…_current_phase)">
        <EntityPicker domains={['sensor']} value={widget.phase_entity} onChange={(v) => onChange({ phase_entity: v })} />
      </Field>
    </>
  );
}

function VideoFields() {
  return (
    <p className="ed-hint">
      Plays what Home Assistant sends to this panel: its Video media player (media_player.play_media with a YouTube or
      video link) or a cast from the YouTube app. Starting a video shows this card's page; switching to another page keeps
      it playing. The button on the card goes full screen. Without a Video card, videos open full screen.
    </p>
  );
}

function MediaPlayerFields({ widget, onChange }) {
  return (
    <>
      <Toggle label="Album art" hint="Beside the controls on wide cards, above them on tall ones, dimmed behind them on small ones"
        checked={widget.show_art !== false} onChange={(v) => onChange({ show_art: v ? undefined : false })} />
      <p className="ed-hint">The card fills any size from one cell up: bigger cards add the output picker, a seek bar and volume, as far as the player supports them. On the panel, long-press the card for the full-screen player.</p>
    </>
  );
}

const COVER_ITEMS = {
  open: 'Open', close: 'Close', stop: 'Stop', position: 'Position slider', presets: 'Position presets',
  tilt_open: 'Tilt open', tilt_close: 'Tilt close', tilt_slider: 'Tilt slider',
};
// Old profiles used coarse groups; writing always migrates to cover_items
function expandGroups(groups) {
  const map = { buttons: ['open', 'stop', 'close'], slider: ['position'], presets: ['presets'], tilt: ['tilt_open', 'tilt_close', 'tilt_slider'] };
  return (groups || []).flatMap((g) => map[g] ?? []);
}

function CoverFields({ widget, onChange }) {
  const items = Array.isArray(widget.cover_items) && widget.cover_items.length ? widget.cover_items : expandGroups(widget.cover_controls);
  const presets = Array.isArray(widget.position_presets) ? widget.position_presets : [0, 25, 75, 100];
  return (
    <>
      <Field label="Controls, in order" hint={items.length ? undefined : 'None picked: whatever the cover supports'}>
        <OrderedList labels={COVER_ITEMS} items={items} onChange={(next) => onChange({ cover_items: next, cover_controls: undefined })} />
      </Field>
      <Field label="Layout">
        <Segmented value={widget.cover_layout || 'auto'} onChange={(v) => onChange({ cover_layout: v })} options={[
          { value: 'auto', label: 'Auto' }, { value: 'horizontal', label: 'Rows' }, { value: 'vertical', label: 'Upright' },
        ]} />
      </Field>
      {items.includes('presets') && (
        <Field label="Preset positions (%)">
          <input key={widget.id} className="ed-input" defaultValue={presets.join(', ')} placeholder="0, 25, 75, 100"
            onBlur={(e) => onChange({ position_presets: e.target.value.split(',').map((s) => parseInt(s.trim(), 10)).filter(Number.isFinite).map((n) => Math.max(0, Math.min(100, n))) })} />
        </Field>
      )}
    </>
  );
}

/** Reorderable subset of `labels` keys, with the rest offered as add chips. */
function OrderedList({ labels, items, onChange }) {
  const rest = Object.keys(labels).filter((k) => !items.includes(k));
  const move = (i, d) => {
    const j = i + d;
    if (j < 0 || j >= items.length) return;
    const next = items.slice();
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {items.map((k, i) => (
        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 2, padding: '2px 2px 2px 10px', borderRadius: 'var(--ed-ctl-radius)', background: 'var(--ed-surface-2)' }}>
          <span style={{ flex: 1, fontSize: 14 }}>{labels[k] ?? k}</span>
          <IconButton path={mdiArrowUp} size={18} className="ed-icon-btn--sm" title="Move up" disabled={i === 0} onClick={() => move(i, -1)} />
          <IconButton path={mdiArrowDown} size={18} className="ed-icon-btn--sm" title="Move down" disabled={i === items.length - 1} onClick={() => move(i, 1)} />
          <IconButton path={mdiClose} size={18} className="ed-icon-btn--sm" title="Remove" onClick={() => onChange(items.filter((x) => x !== k))} />
        </div>
      ))}
      {rest.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
          {rest.map((k) => (
            <button key={k} type="button" className="ed-btn ed-btn--outlined" style={{ height: 30, padding: '0 10px', fontSize: 13 }} onClick={() => onChange([...items, k])}>
              <Icon path={mdiPlus} size={16} />{labels[k]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
