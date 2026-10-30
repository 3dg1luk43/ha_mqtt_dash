import { useDraggable } from '@dnd-kit/core';

export default function PaletteItem({ typeDef, variant = 'list' }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette-${typeDef.type}`,
    data: { dragType: 'new', widgetType: typeDef.type },
  });

  const common = {
    background: isDragging ? 'var(--ed-primary-soft)' : 'var(--ed-surface-2)',
    border: '1px solid var(--ed-divider)',
    cursor: 'grab',
    opacity: isDragging ? 0.5 : 1,
    userSelect: 'none',
  };

  if (variant === 'rail' || variant === 'grid') {
    const rail = variant === 'rail';
    return (
      <div
        ref={setNodeRef}
        {...listeners}
        {...attributes}
        className="ed-pal-tile"
        title={rail ? `${typeDef.label} — ${typeDef.description}` : typeDef.description}
        style={{
          ...common,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 3,
          borderRadius: rail ? 10 : 'var(--ed-ctl-radius)',
          ...(rail ? { width: 42, height: 42 } : { height: 58, padding: '4px 2px' }),
        }}
      >
        <span style={{ fontSize: rail ? 20 : 19, lineHeight: 1 }}>{typeDef.icon}</span>
        {!rail && (
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--ed-text)', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {typeDef.label}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      title={typeDef.description}
      style={{
        ...common,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 10px',
        marginBottom: 4,
        borderRadius: 6,
        fontSize: 13,
      }}
    >
      <span style={{ fontSize: 18 }}>{typeDef.icon}</span>
      <span style={{ fontWeight: 500, color: 'var(--ed-text)' }}>{typeDef.label}</span>
    </div>
  );
}
