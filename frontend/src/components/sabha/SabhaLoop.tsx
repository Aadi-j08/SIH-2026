/** The core story of Sabha, as one line: demand in, impact out. */
import { ArrowRight } from "../Icons";

const STEPS = ["Demand", "AI matching", "Worker allocation", "Job completion", "Agreed price", "Cooperative fund", "Worker & community impact"];

export function SabhaLoop() {
  return (
    <div className="loop" aria-label="How Sabha works">
      {STEPS.map((s, i) => (
        <span key={s} className="row" style={{ gap: 10 }}>
          <span className={`loop-step${i === 1 ? " ai" : ""}`}>{s}</span>
          {i < STEPS.length - 1 && <ArrowRight size={14} style={{ color: "var(--ink-3)" }} />}
        </span>
      ))}
    </div>
  );
}
