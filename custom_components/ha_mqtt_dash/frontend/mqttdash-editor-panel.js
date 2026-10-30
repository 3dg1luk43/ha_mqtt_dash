// Host element for the dashboard editor panel (/mqttdash-editor).
//
// A custom panel instead of HA's built-in "iframe" panel: no HA toolbar, so
// the editor gets the whole content area (everything but the sidebar). On
// narrow layouts (sidebar hidden) a small menu button opens HA's sidebar, and
// the iframe gets data-narrow="1" so the editor can keep that corner free.
class MqttdashEditorPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._narrow = false;
  }

  set hass(_hass) { /* the editor uses window.parent.hassConnection directly */ }
  set panel(panel) { this._panel = panel; this._ensure(); }
  set narrow(narrow) { this._narrow = !!narrow; this._sync(); }

  connectedCallback() { this._ensure(); }

  _ensure() {
    if (this._frame) return;
    const url = (this._panel && this._panel.config && this._panel.config.url) ||
      '/ha_mqtt_dash_static/editor/index.html?embedded=1';
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; position: relative; width: 100%; height: 100vh; height: 100dvh; overflow: hidden;
                background: var(--primary-background-color); }
        iframe { display: block; border: 0; width: 100%; height: 100%; }
        button { position: absolute; top: 8px; left: 8px; width: 40px; height: 40px; border: 0; border-radius: 50%;
                 display: none; align-items: center; justify-content: center; cursor: pointer;
                 background: var(--card-background-color, #1c1c1c); color: var(--primary-text-color, #fff);
                 box-shadow: 0 1px 4px rgba(0,0,0,.35); }
        button svg { width: 22px; height: 22px; fill: currentColor; }
      </style>
      <iframe title="Dashboard editor" allow="clipboard-read; clipboard-write; fullscreen"></iframe>
      <button title="Menu" aria-label="Menu">
        <svg viewBox="0 0 24 24"><path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"/></svg>
      </button>`;
    this._frame = this.shadowRoot.querySelector('iframe');
    this._menu = this.shadowRoot.querySelector('button');
    this._menu.addEventListener('click', () =>
      this.dispatchEvent(new Event('hass-toggle-menu', { bubbles: true, composed: true })));
    // Forward deep-link query (e.g. ?device=kitchen) from the panel URL
    const q = new URLSearchParams(window.location.search);
    const dev = q.get('device');
    this._frame.src = dev ? `${url}${url.includes('?') ? '&' : '?'}device=${encodeURIComponent(dev)}` : url;
    this._sync();
  }

  _sync() {
    if (!this._frame) return;
    this._menu.style.display = this._narrow ? 'flex' : 'none';
    this._frame.dataset.narrow = this._narrow ? '1' : '0';
  }
}

if (!customElements.get('mqttdash-editor-panel')) {
  customElements.define('mqttdash-editor-panel', MqttdashEditorPanel);
}
