// Faint grid cell lines overlaid on the iPad screen

export default function GridOverlay({ grid, width, height }) {
  const cellW = grid.widget_dimensions[0];
  const cellH = grid.widget_dimensions[1];
  const cols = grid.columns;
  const rows = Math.ceil(height / cellH);

  const lines = [];

  // Vertical lines
  for (let c = 1; c < cols; c++) {
    lines.push(
      <line
        key={`v${c}`}
        x1={c * cellW}
        y1={0}
        x2={c * cellW}
        y2={height}
        stroke="#ffffff"
        strokeOpacity="0.06"
        strokeWidth="1"
      />
    );
  }

  // Horizontal lines
  for (let r = 1; r <= rows; r++) {
    lines.push(
      <line
        key={`h${r}`}
        x1={0}
        y1={r * cellH}
        x2={width}
        y2={r * cellH}
        stroke="#ffffff"
        strokeOpacity="0.06"
        strokeWidth="1"
      />
    );
  }

  return (
    <svg
      style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}
      width={width}
      height={height}
    >
      {lines}
    </svg>
  );
}
