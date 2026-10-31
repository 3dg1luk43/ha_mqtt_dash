// Shown when no card is selected: grid and navigation bar.
import { mdiAlertOutline, mdiInformationOutline } from '@mdi/js';
import { useEditorStore, effectiveGrid } from '../../store/editorStore';
import { NAV_H, NAV_W } from '../../utils/frameGeometry';
import { Section, Field, NumberInput, Toggle, Segmented, ColorField, Icon } from '../ui';

const NAV_COLORS = [
  ['bgColor', 'Bar'], ['activeColor', 'Current page'], ['inactiveColor', 'Other pages'],
  ['textColor', 'Text'], ['borderColor', 'Border'],
];

export default function LayoutSettings() {
  const {
    grid, setGridConfig, setPageGrid, pages, activePageIndex, device, orientation,
    navbar_edge, setNavbarEdge, navbar_style = {}, setNavbarStyle,
    navbar_show_battery = true, navbar_show_keepawake = true, setNavbarShowBattery, setNavbarShowKeepAwake,
  } = useEditorStore();

  const page = pages[activePageIndex];
  const own = !!page?.grid;
  const g = effectiveGrid(grid, page);
  const patch = (p) => (own ? setPageGrid(activePageIndex, p) : setGridConfig(p));

  const [pw, ph] = device.points ?? [768, 1024];
  const [screenW, screenH] = orientation === 'landscape' ? [ph, pw] : [pw, ph];
  const vertical = navbar_edge === 'left' || navbar_edge === 'right';
  const contentW = vertical ? screenW - NAV_W : screenW;
  const contentH = vertical ? screenH : screenH - NAV_H;
  const [cellW, cellH] = g.widget_dimensions;
  const rowsFit = Math.floor(contentH / cellH);
  const fillW = Math.floor(contentW / g.columns);

  const widgets = page?.widgets ?? [];
  const overflowX = widgets.some((w) => (w.x + w.w) * cellW > contentW);
  const overflowY = widgets.some((w) => (w.y + w.h) * cellH > contentH);

  function fitToScreen() {
    const rows = Math.max(rowsFit, widgets.reduce((m, w) => Math.max(m, w.y + w.h), 1));
    patch({ widget_dimensions: [fillW, Math.floor(contentH / rows)] });
  }

  return (
    <>
      <Section title="Grid" note={own ? `${page.name} only` : 'all pages'}>
        <Toggle label={`Own grid for “${page?.name}”`} hint="Otherwise every page shares one grid"
          checked={own} onChange={(on) => setPageGrid(activePageIndex, on ? { ...grid } : null)} />
        <Field label="Columns" inline>
          <NumberInput min={1} max={24} value={g.columns}
            onChange={(v) => patch({ columns: Math.max(1, Math.round(v)) })} width={72} />
        </Field>
        <p className="ed-hint">{g.columns} × {rowsFit} cells of {cellW}×{cellH} pt fit on the screen.</p>
        {(overflowX || overflowY) && (
          <div className="ed-callout ed-callout--warn">
            <Icon path={mdiAlertOutline} size={18} />
            <div>
              Some cards run past the {overflowX && overflowY ? 'right and bottom edges' : overflowX ? 'right edge' : 'bottom edge'} of the screen.
              <button type="button" className="ed-btn" style={{ height: 30, padding: '0 8px', marginTop: 4 }} onClick={fitToScreen}>Shrink cells to fit</button>
            </div>
          </div>
        )}
      </Section>

      <Section title="Cell size and spacing" collapsible>
        <Field label="Cell width (pt)" hint={cellW !== fillW ? `${fillW} pt fills the screen width` : 'Fills the screen width'}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <NumberInput min={20} value={cellW} onChange={(v) => patch({ widget_dimensions: [Math.round(v), cellH] })} />
            {cellW !== fillW && <button type="button" className="ed-btn" style={{ height: 32 }} onClick={() => patch({ widget_dimensions: [fillW, cellH] })}>Fill width</button>}
          </div>
        </Field>
        <Field label="Cell height (pt)">
          <NumberInput min={20} value={cellH} onChange={(v) => patch({ widget_dimensions: [cellW, Math.round(v)] })} />
        </Field>
        <div className="ed-row">
          <Field label="Gap across (pt)"><NumberInput min={0} max={40} value={g.widget_margins[0]} onChange={(v) => patch({ widget_margins: [Math.round(v), g.widget_margins[1]] })} width="100%" /></Field>
          <Field label="Gap down (pt)"><NumberInput min={0} max={40} value={g.widget_margins[1]} onChange={(v) => patch({ widget_margins: [g.widget_margins[0], Math.round(v)] })} width="100%" /></Field>
        </div>
      </Section>

      <Section title="Navigation bar">
        <Field label="Position">
          <Segmented value={navbar_edge} onChange={setNavbarEdge} options={[
            { value: 'top', label: 'Top' }, { value: 'bottom', label: 'Bottom' }, { value: 'left', label: 'Left' }, { value: 'right', label: 'Right' },
          ]} />
        </Field>
        <Toggle label="Battery level" checked={navbar_show_battery} onChange={setNavbarShowBattery} />
        <Toggle label="Keep-awake button" checked={navbar_show_keepawake} onChange={setNavbarShowKeepAwake} />
      </Section>

      <Section title="Navigation bar colors" collapsible note={Object.keys(navbar_style).length ? 'customized' : undefined}>
        <div className="ed-row">
          {NAV_COLORS.map(([k, label]) => (
            <ColorField key={k} label={label} value={navbar_style[k]} onChange={(v) => setNavbarStyle({ [k]: v })} />
          ))}
        </div>
      </Section>

      <div className="ed-callout" style={{ marginTop: 12 }}>
        <Icon path={mdiInformationOutline} size={18} />
        <div>Keep awake, brightness, screensaver and orientation are set on the panel's device page in Home Assistant.</div>
      </div>
    </>
  );
}
