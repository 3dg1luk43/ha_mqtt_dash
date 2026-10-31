// Settings for the selected card: what it shows, how it looks, where it sits.
import { mdiDeleteOutline, mdiFormatAlignLeft, mdiFormatAlignCenter, mdiFormatAlignRight, mdiFormatAlignTop, mdiFormatAlignMiddle, mdiFormatAlignBottom } from '@mdi/js';
import { useEditorStore } from '../../store/editorStore';
import { typeDef, FORMAT_OPTIONS, FORMAT_LABELS } from '../../data/widgetTypes';
import EntityPicker from './EntityPicker';
import CardFields from './CardFields';
import { Section, Field, TextInput, NumberInput, Toggle, Segmented, ColorField, Icon } from '../ui';

// Cards whose main entity lives in entity_id (camera and printer use their own fields)
const PRIMARY_ENTITY = {
  light: 'Light', switch: 'Entity', scene: 'Scene, script or button', button: 'Scene, script or button',
  cover: 'Cover', climate: 'Thermostat', sensor: 'Entity', value: 'Entity', person: 'Person',
  weather: 'Weather entity', mediaplayer: 'Media player', sousvide: 'Cooker state', appliance: 'Running state',
};
const PROTECTABLE = ['light', 'switch', 'scene', 'button', 'cover'];

export default function WidgetSettings({ widget }) {
  const { updateWidget, removeWidget } = useEditorStore();
  const def = typeDef(widget.type);
  const set = (patch) => updateWidget(widget.id, patch);
  const formatKeys = def?.format ?? [];

  return (
    <>
      <Section title="Card">
        <Field label="Name" hint="Shown on the card">
          <TextInput value={widget.label} onChange={(v) => set({ label: v })} placeholder={def?.label} />
        </Field>
        {PRIMARY_ENTITY[widget.type] && (
          <Field label={PRIMARY_ENTITY[widget.type]}>
            <EntityPicker domains={def?.domains} value={widget.entity_id} onChange={(v) => set({ entity_id: v })} />
          </Field>
        )}
        <CardFields widget={widget} onChange={set} />
        {PROTECTABLE.includes(widget.type) && (
          <Toggle label="Ask before switching" hint="A confirmation appears on the panel first"
            checked={!!widget.protected} onChange={(v) => set({ protected: v || undefined })} />
        )}
      </Section>

      {formatKeys.length > 0 && (
        <Section title="Appearance" collapsible note={Object.keys(widget.format ?? {}).length ? 'customized' : undefined}>
          <FormatFields keys={formatKeys} type={widget.type} format={widget.format ?? {}} onChange={(format) => set({ format })} />
        </Section>
      )}

      <Section title="Position and size" collapsible note={`${widget.w}×${widget.h} at ${widget.x}, ${widget.y}`}>
        <div className="ed-row">
          <Field label="Column"><NumberInput min={0} value={widget.x} onChange={(v) => set({ x: Math.max(0, Math.round(v)) })} width="100%" /></Field>
          <Field label="Row"><NumberInput min={0} value={widget.y} onChange={(v) => set({ y: Math.max(0, Math.round(v)) })} width="100%" /></Field>
          <Field label="Width (cells)"><NumberInput min={1} value={widget.w} onChange={(v) => set({ w: Math.max(1, Math.round(v)) })} width="100%" /></Field>
          <Field label="Height (cells)"><NumberInput min={1} value={widget.h} onChange={(v) => set({ h: Math.max(1, Math.round(v)) })} width="100%" /></Field>
        </div>
        <p className="ed-hint">Or drag the card, and its bottom-right corner, on the canvas.</p>
      </Section>

      <div style={{ paddingTop: 12 }}>
        <button type="button" className="ed-btn ed-btn--danger ed-btn--block" onClick={() => removeWidget(widget.id)}>
          <Icon path={mdiDeleteOutline} size={18} />Remove card
        </button>
      </div>
    </>
  );
}

function FormatFields({ keys, type, format, onChange }) {
  const labels = { ...Object.fromEntries(Object.entries(FORMAT_OPTIONS).map(([k, o]) => [k, o.label])), ...(FORMAT_LABELS[type] ?? {}) };
  const setKey = (k, v) => {
    const next = { ...format, [k]: v };
    if (v === undefined || v === '' || v === null) delete next[k];
    onChange(next);
  };
  const colors = keys.filter((k) => FORMAT_OPTIONS[k]?.kind === 'color');
  return (
    <>
      {keys.includes('align') && (
        <Field label={labels.align}>
          <Segmented value={format.align ?? ''} onChange={(v) => setKey('align', v)} options={[
            { value: 'left', icon: mdiFormatAlignLeft, title: 'Left' },
            { value: 'center', icon: mdiFormatAlignCenter, title: 'Center' },
            { value: 'right', icon: mdiFormatAlignRight, title: 'Right' },
          ]} />
        </Field>
      )}
      {keys.includes('vAlign') && (
        <Field label={labels.vAlign}>
          <Segmented value={format.vAlign ?? ''} onChange={(v) => setKey('vAlign', v)} options={[
            { value: 'top', icon: mdiFormatAlignTop, title: 'Top' },
            { value: 'middle', icon: mdiFormatAlignMiddle, title: 'Middle' },
            { value: 'bottom', icon: mdiFormatAlignBottom, title: 'Bottom' },
          ]} />
        </Field>
      )}
      {keys.includes('textSize') && (
        <Field label={`${labels.textSize} (pt)`} hint="Empty: sized to fit the card">
          <NumberInput allowEmpty min={8} max={160} value={format.textSize} placeholder="auto" onChange={(v) => setKey('textSize', v)} />
        </Field>
      )}
      {keys.includes('wrap') && (
        <Toggle label={labels.wrap} checked={!!format.wrap} onChange={(v) => setKey('wrap', v || undefined)} />
      )}
      {keys.includes('maxLines') && format.wrap && (
        <Field label={labels.maxLines}>
          <NumberInput allowEmpty min={1} max={20} value={format.maxLines} placeholder="all" onChange={(v) => setKey('maxLines', v)} />
        </Field>
      )}
      {colors.length > 0 && (
        <div className="ed-row">
          {colors.map((k) => <ColorField key={k} label={labels[k]} value={format[k]} onChange={(v) => setKey(k, v)} />)}
        </div>
      )}
    </>
  );
}
