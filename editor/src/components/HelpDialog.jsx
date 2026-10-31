import { Dialog } from './ui';

export default function HelpDialog({ onClose }) {
  return (
    <Dialog title="Using the editor" onClose={onClose} width={560}
      actions={<button type="button" className="ed-btn ed-btn--filled" onClick={onClose}>Done</button>}>
      <p>The canvas is the selected panel's screen. Changes stay in this browser until you deploy them.</p>

      <h3>Adding cards</h3>
      <ul>
        <li>Search for an entity on the left and drag it onto the screen. The card type follows the entity: a light becomes a light card, a thermostat a climate card.</li>
        <li>Without a search, pick a card type. Click instead of dragging to drop it in the first free spot.</li>
      </ul>

      <h3>Arranging</h3>
      <ul>
        <li>Drag a card to move it; drag its bottom-right corner to resize it. A red outline means it overlaps another card.</li>
        <li>Click a card to edit it on the right. Click empty space for the grid and navigation bar.</li>
        <li>Pages are the tabs in the screen's navigation bar: <strong>+</strong> adds one, double-click renames it.</li>
      </ul>

      <h3>Load and Deploy</h3>
      <ul>
        <li><strong>Load</strong> replaces the canvas with the layout the panel is showing now.</li>
        <li><strong>Deploy</strong> sends the canvas to the panel; it redraws within a few seconds. A dot on the button means there are changes the panel doesn't have yet.</li>
        <li><strong>Profile JSON</strong> in the menu copies or downloads the layout, and loads a saved one back.</li>
      </ul>

      <h3>Shortcuts</h3>
      <ul>
        <li><kbd>Ctrl</kbd> + <kbd>Z</kbd> undo, <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Z</kbd> or <kbd>Ctrl</kbd> + <kbd>Y</kbd> redo</li>
        <li><kbd>Delete</kbd> removes the selected card, <kbd>Esc</kbd> deselects it</li>
      </ul>

      <p className="ed-hint">Keep awake, brightness, screensaver and orientation are panel settings: change them on the panel's device page in Home Assistant.</p>
    </Dialog>
  );
}
