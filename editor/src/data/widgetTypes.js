// Card types the iPad app renders. `group` orders the add panel, `domains`
// filters the entity picker and maps a dropped HA entity to a card, `size` is
// the default footprint in cells, `format` lists the format keys the app's
// card actually reads (see FORMAT_OPTIONS). `hidden` types still load from old
// profiles but aren't offered for new cards (the app renders them like another type).
import {
  mdiLightbulbOutline, mdiToggleSwitchOutline, mdiPalette, mdiGauge, mdiAccountOutline,
  mdiGestureTapButton, mdiFormatText, mdiClockOutline, mdiWeatherPartlyCloudy, mdiThermostat,
  mdiCctv, mdiPrinter3dNozzleOutline, mdiTimerOutline, mdiWeb, mdiChefHat, mdiPotSteamOutline,
  mdiWashingMachine, mdiMusicNote, mdiBlindsHorizontal, mdiTelevisionPlay,
} from '@mdi/js';

const TOGGLE_FORMAT = ['align', 'vAlign', 'textSize', 'onBgColor', 'onTextColor', 'offBgColor', 'offTextColor'];
const TEXT_FORMAT = ['align', 'vAlign', 'textSize', 'wrap', 'textColor', 'bgColor'];

export const GROUPS = [
  { key: 'controls', label: 'Controls' },
  { key: 'info', label: 'Information' },
  { key: 'media', label: 'Media' },
  { key: 'kitchen', label: 'Kitchen & appliances' },
];

export const WIDGET_TYPES = [
  {
    type: 'light', label: 'Light', icon: mdiLightbulbOutline, group: 'controls', size: [1, 1],
    description: 'Tap to switch, drag across the card to dim',
    domains: ['light'], format: TOGGLE_FORMAT,
  },
  {
    type: 'switch', label: 'Switch', icon: mdiToggleSwitchOutline, group: 'controls', size: [1, 1],
    description: 'On/off for switches, helpers, fans and automations',
    domains: ['switch', 'input_boolean', 'fan', 'automation', 'siren', 'humidifier'], format: TOGGLE_FORMAT,
  },
  {
    type: 'scene', label: 'Scene or script', icon: mdiPalette, group: 'controls', size: [1, 1],
    description: 'Runs a scene, script or button entity',
    domains: ['scene', 'script', 'button', 'input_button'], format: TOGGLE_FORMAT,
  },
  {
    type: 'cover', label: 'Cover', icon: mdiBlindsHorizontal, group: 'controls', size: [1, 1],
    description: 'Blinds, shades and garage doors: open, close, stop, position',
    domains: ['cover'], format: ['textColor'],
  },
  {
    type: 'climate', label: 'Climate', icon: mdiThermostat, group: 'controls', size: [2, 1],
    description: 'Current and target temperature with mode buttons',
    domains: ['climate', 'water_heater'], format: [],
  },
  {
    type: 'sensor', label: 'Sensor', icon: mdiGauge, group: 'info', size: [1, 1],
    description: 'Shows an entity state with its unit',
    domains: ['sensor', 'binary_sensor', 'number', 'input_number', 'input_select', 'select', 'input_text', 'counter', 'lock', 'alarm_control_panel', 'vacuum', 'update'],
    format: [...TEXT_FORMAT, 'maxLines'],
  },
  {
    type: 'person', label: 'Person', icon: mdiAccountOutline, group: 'info', size: [1, 1],
    description: 'Where someone is',
    domains: ['person', 'device_tracker'], format: [...TEXT_FORMAT, 'maxLines'],
  },
  {
    type: 'weather', label: 'Weather', icon: mdiWeatherPartlyCloudy, group: 'info', size: [2, 1],
    description: 'Selected attributes of a weather entity',
    domains: ['weather'], format: ['textSize', 'textColor', 'bgColor'],
  },
  {
    type: 'clock', label: 'Clock', icon: mdiClockOutline, group: 'info', size: [2, 1],
    description: 'The panel\'s local time',
    domains: [], format: ['align', 'vAlign', 'textSize', 'textColor', 'bgColor'],
  },
  {
    type: 'label', label: 'Text', icon: mdiFormatText, group: 'info', size: [2, 1],
    description: 'Fixed text',
    domains: [], format: [...TEXT_FORMAT, 'maxLines'],
  },
  {
    type: 'mediaplayer', label: 'Media player', icon: mdiMusicNote, group: 'media', size: [2, 2],
    description: 'Playback, seek, volume and output; fits any card size',
    domains: ['media_player'], format: [],
  },
  {
    type: 'camera', label: 'Camera', icon: mdiCctv, group: 'media', size: [2, 2],
    description: 'Camera entity relayed by Home Assistant, or a direct MJPEG/JPEG URL',
    domains: ['camera'], format: ['onBgColor', 'onTextColor', 'offBgColor', 'offTextColor'],
  },
  {
    type: 'video', label: 'Video', icon: mdiTelevisionPlay, group: 'media', size: [4, 3],
    description: 'Videos cast or played from Home Assistant; keeps playing on other pages',
    domains: [], format: [],
  },
  {
    type: 'webpage', label: 'Web page', icon: mdiWeb, group: 'media', size: [2, 2],
    description: 'Embeds a web page',
    domains: [], format: [],
  },
  {
    type: 'timer', label: 'Timer', icon: mdiTimerOutline, group: 'kitchen', size: [1, 1],
    description: 'Countdown on the panel itself, with saved quick picks',
    domains: [], format: ['textColor'],
  },
  {
    type: 'mealie', label: 'Mealie recipes', icon: mdiChefHat, group: 'kitchen', size: [3, 4],
    description: 'Recipes from a self-hosted Mealie, readable next to the timers',
    domains: [], format: ['textSize'],
  },
  {
    type: 'sousvide', label: 'Sous vide', icon: mdiPotSteamOutline, group: 'kitchen', size: [2, 1],
    description: 'Cooker state, water and target temperature, time left',
    domains: ['sensor', 'binary_sensor', 'switch', 'climate'], format: ['textSize'],
  },
  {
    type: 'appliance', label: 'Appliance', icon: mdiWashingMachine, group: 'kitchen', size: [2, 1],
    description: 'Washer, dryer or dishwasher: program, phase, time left',
    domains: ['sensor', 'binary_sensor', 'switch', 'select'], format: ['textSize'],
  },
  {
    type: 'printer', label: '3D printer', icon: mdiPrinter3dNozzleOutline, group: 'kitchen', size: [2, 2],
    description: 'Print status, progress, temperatures and preview',
    domains: ['sensor'], format: ['textSize'],
  },
  // Older profiles: rendered by the app exactly like sensor / scene.
  {
    type: 'value', label: 'Sensor', icon: mdiGauge, group: 'info', size: [1, 1], hidden: true,
    description: 'Shows an entity state with its unit', domains: ['sensor'], format: [...TEXT_FORMAT, 'maxLines'],
  },
  {
    type: 'button', label: 'Button', icon: mdiGestureTapButton, group: 'controls', size: [1, 1], hidden: true,
    description: 'Runs a scene, script or button entity', domains: ['scene', 'script', 'button', 'input_button'], format: TOGGLE_FORMAT,
  },
];

export const typeDef = (type) => WIDGET_TYPES.find((t) => t.type === type);

// Dropping an HA entity: the first visible card type that lists its domain.
// Anything else shows its state on a sensor card.
export function cardTypeForEntity(entityId) {
  const domain = String(entityId).split('.')[0];
  const t = WIDGET_TYPES.find((d) => !d.hidden && d.domains[0] === domain)
    ?? WIDGET_TYPES.find((d) => !d.hidden && d.domains.includes(domain) && !['sousvide', 'appliance', 'printer'].includes(d.type));
  return t?.type ?? 'sensor';
}

// Format keys → editor control. Labels follow what the app does with them.
export const FORMAT_OPTIONS = {
  align: { kind: 'align', label: 'Horizontal alignment' },
  vAlign: { kind: 'valign', label: 'Vertical alignment' },
  textSize: { kind: 'size', label: 'Text size' },
  wrap: { kind: 'wrap', label: 'Wrap long text' },
  maxLines: { kind: 'lines', label: 'Max lines' },
  textColor: { kind: 'color', label: 'Text color' },
  bgColor: { kind: 'color', label: 'Background' },
  onBgColor: { kind: 'color', label: 'On: background' },
  onTextColor: { kind: 'color', label: 'On: text' },
  offBgColor: { kind: 'color', label: 'Off: background' },
  offTextColor: { kind: 'color', label: 'Off: text' },
};

// Card-specific wording for the shared keys
export const FORMAT_LABELS = {
  timer: { textColor: 'Accent color' },
  camera: { onBgColor: 'Overlay button on', onTextColor: 'Overlay text on', offBgColor: 'Overlay button off', offTextColor: 'Overlay text off' },
  cover: { textColor: 'Status text color' },
};
