/**
 * How the cooperative fund is allocated: one pie, four slices, a legend
 * with percentages and rupees. Colours are literal, assigned in a fixed
 * order (validated for colour-vision safety), never cycled; text stays ink.
 */
import { useState } from "react";

import { formatRupees } from "../../api";

const SLICE_COLOURS = ["#435ab8", "#25984d", "#e0a028", "#8a8fd9", "#8c857f", "#c65d26"];

export function FundPie({ allocation, total, size = 168 }: { allocation: Record<string, number>; total: number; size?: number }) {
  const entries = Object.entries(allocation).filter(([, pct]) => pct > 0);
  const [hover, setHover] = useState<number | null>(null);
  const r = size / 2;
  const ring = r * 0.34;                      // stroke width → a donut with a readable hole
  const radius = r - ring / 2 - 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="pie">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Fund allocation">
        <title>Fund allocation</title>
        {entries.map(([name, pct], i) => {
          const len = (pct / 100) * circumference;
          const gap = 2;                       // a 2px surface gap between slices
          const dash = `${Math.max(0, len - gap)} ${circumference - Math.max(0, len - gap)}`;
          const el = (
            <circle
              key={name}
              cx={r}
              cy={r}
              r={radius}
              fill="none"
              stroke={SLICE_COLOURS[i % SLICE_COLOURS.length]}
              strokeWidth={hover === i ? ring + 4 : ring}
              strokeDasharray={dash}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${r} ${r})`}
              opacity={hover === null || hover === i ? 1 : 0.45}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              style={{ transition: "stroke-width 120ms ease, opacity 120ms ease" }}
            >
              <title>{`${name}: ${pct}% · ${formatRupees((total * pct) / 100)}`}</title>
            </circle>
          );
          offset += len;
          return el;
        })}
        <text x={r} y={r - 4} textAnchor="middle" style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, fill: "var(--ink)" }}>
          {hover === null ? formatRupees(total) : `${entries[hover][1]}%`}
        </text>
        <text x={r} y={r + 14} textAnchor="middle" style={{ fontSize: 11, fill: "var(--ink-3)" }}>
          {hover === null ? "in the fund" : entries[hover][0].split(" ")[0]}
        </text>
      </svg>
      <ul className="pie-legend">
        {entries.map(([name, pct], i) => (
          <li key={name} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} style={{ opacity: hover === null || hover === i ? 1 : 0.55 }}>
            <i style={{ background: SLICE_COLOURS[i % SLICE_COLOURS.length] }} />
            <span className="grow">{name}</span>
            <span className="num" style={{ fontWeight: 700 }}>{pct}%</span>
            <span className="num muted small">{formatRupees((total * pct) / 100)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
