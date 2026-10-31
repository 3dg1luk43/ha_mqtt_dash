// Small shared controls, styled after Home Assistant's (see App.css .ed-*).
import { useEffect, useRef, useState } from 'react';
import { HexColorPicker } from 'react-colorful';
import { mdiChevronDown, mdiChevronRight, mdiClose } from '@mdi/js';

export function Icon({ path, size = 20, color = 'currentColor', style, title }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}
      style={{ flexShrink: 0, display: 'block', ...style }}>
      {title && <title>{title}</title>}
      <path d={path} fill={color} />
    </svg>
  );
}

export function IconButton({ path, title, onClick, disabled, pressed, size = 20, className = '', ...rest }) {
  return (
    <button type="button" className={`ed-btn ed-icon-btn ${className}`} onClick={onClick} disabled={disabled}
      title={title} aria-label={title} aria-pressed={pressed} {...rest}>
      <Icon path={path} size={size} />
    </button>
  );
}

/** Titled block; `collapsible` ones start closed unless `defaultOpen`. */
export function Section({ title, children, collapsible = false, defaultOpen = false, note }) {
  const [open, setOpen] = useState(!collapsible || defaultOpen);
  return (
    <section className="ed-section">
      {collapsible ? (
        <button type="button" className="ed-section-head ed-section-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
          <Icon path={open ? mdiChevronDown : mdiChevronRight} size={18} />
          <span>{title}</span>
          {note && <span className="ed-section-note">{note}</span>}
        </button>
      ) : (
        <h3 className="ed-section-head">{title}{note && <span className="ed-section-note">{note}</span>}</h3>
      )}
      {open && <div className="ed-section-body">{children}</div>}
    </section>
  );
}

/** Label above its control; `inline` puts a short control on the right. */
export function Field({ label, hint, children, inline = false }) {
  return (
    <div className={`ed-field ${inline ? 'ed-field--inline' : ''}`}>
      {label && <label className="ed-label">{label}</label>}
      <div className="ed-field-control">{children}</div>
      {hint && <div className="ed-hint">{hint}</div>}
    </div>
  );
}

export function TextInput({ value, onChange, placeholder, mono = false, type = 'text', ...rest }) {
  return (
    <input className={`ed-input ${mono ? 'ed-input--mono' : ''}`} type={type} value={value ?? ''} placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)} {...rest} />
  );
}

/** Number input that allows clearing (onChange(undefined)) when `allowEmpty`. */
export function NumberInput({ value, onChange, min, max, step = 1, placeholder, allowEmpty = false, width = 88 }) {
  return (
    <input className="ed-input" type="number" value={value ?? ''} min={min} max={max} step={step} placeholder={placeholder}
      style={{ width }}
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === '') return allowEmpty ? onChange(undefined) : undefined;
        const v = Number(raw);
        if (Number.isFinite(v)) onChange(v);
      }} />
  );
}

export function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="ed-toggle">
      <span className="ed-toggle-text">
        <span>{label}</span>
        {hint && <span className="ed-hint">{hint}</span>}
      </span>
      <input type="checkbox" className="ed-switch" checked={!!checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}

/** options: [{ value, label?, icon?, title? }] */
export function Segmented({ value, options, onChange, ariaLabel }) {
  return (
    <span className="ed-seg" role="group" aria-label={ariaLabel}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} title={o.title ?? o.label}
          onClick={() => onChange(o.value)} className={o.label ? 'ed-seg-text' : undefined}>
          {o.icon ? <Icon path={o.icon} size={18} /> : o.label}
        </button>
      ))}
    </span>
  );
}

/** Swatch + hex text + popover picker; empty means "card default". */
export function ColorField({ label, value, onChange, placeholder = 'default' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);
  return (
    <div className="ed-color" ref={ref}>
      <span className="ed-label">{label}</span>
      <div className="ed-color-row">
        <button type="button" className="ed-swatch" style={{ background: value || undefined }} onClick={() => setOpen(!open)}
          title={value || 'Card default'} aria-label={`${label}: ${value || 'default'}`} />
        <input className="ed-input ed-input--mono" value={value ?? ''} placeholder={placeholder}
          onChange={(e) => onChange(e.target.value.trim() || undefined)} />
        {value && <IconButton path={mdiClose} size={16} title="Use the card default" onClick={() => onChange(undefined)} className="ed-icon-btn--sm" />}
      </div>
      {open && (
        <div className="ed-popover">
          <HexColorPicker color={/^#[0-9a-f]{6}$/i.test(value ?? '') ? value : '#ffffff'} onChange={onChange} />
        </div>
      )}
    </div>
  );
}

export function Dialog({ title, onClose, children, actions, width = 560 }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="ed-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="ed-dialog" role="dialog" aria-modal="true" aria-label={title} style={{ width }}>
        <header className="ed-dialog-head">
          <h2>{title}</h2>
          <IconButton path={mdiClose} title="Close" onClick={onClose} />
        </header>
        <div className="ed-dialog-body">{children}</div>
        {actions && <footer className="ed-dialog-foot">{actions}</footer>}
      </div>
    </div>
  );
}
