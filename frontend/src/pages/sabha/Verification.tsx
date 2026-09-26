/** Council verification checklist: every unverified skill, certificate and portfolio item in the cooperative. */
import { useCallback, useEffect, useState } from "react";

import { api, errorMessage, type Worker } from "../../api";
import { Check, Cross } from "../../components/Icons";

export default function Verification() {
   const [workers, setWorkers] = useState<Worker[] | null>(null);
  const [pendingWorkers, setPendingWorkers] = useState<Worker[] | null>(null);
  const [items, setItems] = useState<ProfileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const ws = await api.workers.list();
      setWorkers(ws);
      const pending = await api.workers.pending();
      setPendingWorkers(pending);
      const collected: ProfileItem[] = [];
      for (const w of ws) {
        const p = await api.workers.profile(w.id);
        for (const s of p.skills) if (!s.verified) collected.push({ kind: "skill", workerId: w.id, workerName: w.name, id: s.id, label: s.name });
        for (const c of p.certifications) if (!c.verified) collected.push({ kind: "cert", workerId: w.id, workerName: w.name, id: c.id, label: c.name });
        for (const p2 of p.portfolio) if (!p2.verified) collected.push({ kind: "portfolio", workerId: w.id, workerName: w.name, id: p2.id, label: p2.caption ?? "portfolio item" });
      }
      setItems(collected);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const verify = async (w: Worker, kind: "skill" | "cert" | "portfolio", id: number) => {
    setLoading(true);
    try {
      if (kind === "skill") {
        await api.workers.skills.verify(w.id, id, true);
      } else if (kind === "cert") {
        await api.workers.certifications.verify(w.id, id, true);
      } else {
        await api.workers.portfolio.verify(w.id, id, true);
      }
      setItems((prev) => prev.filter((it) => !(it.kind === kind && it.id === id)));
    } catch (e) {
      alert(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const approve = async (id: number) => {
    setLoading(true);
    try {
      await api.workers.approve(id, "active");
      setPendingWorkers((prev) => (prev ? prev.filter((w) => w.id !== id) : prev));
    } catch (e) {
      alert(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const reject = async (id: number) => {
    if (!confirm("Reject this worker's application? They will not receive jobs.")) return;
    setLoading(true);
    try {
      await api.workers.approve(id, "rejected");
      setPendingWorkers((prev) => (prev ? prev.filter((w) => w.id !== id) : prev));
    } catch (e) {
      alert(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page wide sabha-page">
      <h1>Verification checklist</h1>
      {error && <div className="notice error">{error}</div>}
      {loading && <div className="small muted">Saving…</div>}
      {!workers ? (
        <div className="small muted">Loading…</div>
      ) : items.length === 0 ? (
        <div className="small muted">All profile items in this cooperative are verified.</div>
      ) : (
        <div className="table">
          <div className="trow head t4">
            <span>Worker</span>
            <span>Item</span>
            <span>Type</span>
            <span style={{ flex: "32px" }}>Verify</span>
          </div>
          {items.map((it) => {
            const worker = workers.find((w) => w.id === it.workerId);
            return (
              <div className="trow t4" key={`${it.kind}-${it.id}`}>
                <span>{worker?.name ?? `Worker #${it.workerId}`}</span>
                <span>{it.label}</span>
                <span className="small muted">{it.kind}</span>
                <button
                  className="chip on"
                  onClick={() => worker && verify(worker, it.kind, it.id)}
                  disabled={loading}
                  title="Mark verified"
                >
                  <Check />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {pendingWorkers && pendingWorkers.length > 0 && (
        <section className="card" style={{ marginTop: 24 }}>
          <h2 style={{ marginTop: 0 }}>Pending worker applications ({pendingWorkers.length})</h2>
          <div className="table">
            <div className="trow head t4">
              <span>Worker</span>
              <span>Trade · Phone</span>
              <span style={{ justifyContent: "flex-end" }}>Verify</span>
            </div>
            {pendingWorkers.map((w) => (
              <div className="trow t4" key={w.id}>
                <span>{w.name}</span>
                <span className="small muted">{w.trade} · {w.phone ?? "—"}</span>
                <div className="row" style={{ justifyContent: "flex-end", gap: 6 }}>
                  <button className="chip on" onClick={() => approve(w.id)} disabled={loading} title="Approve"><Check /></button>
                  <button className="chip off" onClick={() => reject(w.id)} disabled={loading} title="Reject"><Cross /></button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

interface ProfileItem {
  kind: "skill" | "cert" | "portfolio";
  workerId: number;
  workerName: string;
  id: number;
  label: string;
}
