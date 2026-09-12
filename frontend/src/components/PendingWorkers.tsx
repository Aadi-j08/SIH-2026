import { useEffect, useState } from "react";

import { api, errorMessage, titleCase, type Worker } from "../api";
import { Check } from "./Icons";

/**
 * Sabha: Kaam sign-ups waiting for approval. Until a council member approves
 * them the allocation engine does not offer them work. Renders nothing when
 * the queue is empty.
 */
export default function PendingWorkers({ onApproved }: { onApproved?: () => void }) {
  const [pending, setPending] = useState<Worker[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.kaam.pending().then(setPending).catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const approve = async (worker: Worker) => {
    setBusy(worker.id);
    setError(null);
    try {
      await api.kaam.approve(worker.id);
      setPending((list) => list.filter((w) => w.id !== worker.id));
      onApproved?.();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  if (pending.length === 0 && !error) return null;

  return (
    <div className="panel" style={{ borderColor: "#e9c46a", background: "#fffaf0" }}>
      <div className="row between" style={{ flexWrap: "wrap", gap: 8 }}>
        <div className="stack" style={{ gap: 2 }}>
          <h2>Waiting for approval · {pending.length}</h2>
          <div className="small muted">New Kaam sign-ups. The engine offers them work only after a council member approves them.</div>
        </div>
      </div>
      {error && <div className="notice error">{error}</div>}
      <div className="stack" style={{ gap: 6 }}>
        {pending.map((w) => (
          <div key={w.id} className="card row" style={{ gap: 12, flexWrap: "wrap" }}>
            <div className="stack grow" style={{ gap: 1 }}>
              <span style={{ fontWeight: 700 }}>{w.name}</span>
              <span className="tiny muted">
                {titleCase(w.trade)}{w.phone ? ` · ${w.phone}` : ""} · signed up {w.created_at ? new Date(w.created_at.replace(" ", "T") + "Z").toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""}
                {w.availability.length > 0 ? ` · ${w.availability.length} availability window${w.availability.length === 1 ? "" : "s"} set` : " · no availability yet"}
              </span>
            </div>
            {w.phone && (
              <a href={`tel:${w.phone}`} className="btn small outline">Call</a>
            )}
            <button type="button" className="btn small primary" disabled={busy === w.id} onClick={() => approve(w)}>
              <Check size={14} strokeWidth={3} /> {busy === w.id ? "Approving…" : "Approve"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
