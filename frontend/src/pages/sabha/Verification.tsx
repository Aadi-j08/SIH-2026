/** Council verification checklist: every unverified skill, certificate and portfolio item in the cooperative. */
import { useCallback, useEffect, useState } from "react";

import { api, errorMessage, titleCase, type Worker, type WorkerDocument } from "../../api";
import { Check, Cross } from "../../components/Icons";

export default function Verification() {
   const [workers, setWorkers] = useState<Worker[] | null>(null);
  const [pendingWorkers, setPendingWorkers] = useState<Worker[] | null>(null);
  const [aadhaarByWorker, setAadhaarByWorker] = useState<Record<number, boolean>>({});
  const [items, setItems] = useState<ProfileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const ws = await api.workers.list();
      setWorkers(ws);
      const pending = await api.workers.pending();
      setPendingWorkers(pending);
      // Verify each pending worker has a *verified* Aadhaar (required to activate).
      const aadhaarMap: Record<number, boolean> = {};
      for (const w of pending) {
        try {
          const docs = await api.workers.documents.list(w.id);
          aadhaarMap[w.id] = docs.some((d) => d.document_type === "aadhaar" && d.verified);
        } catch {
          aadhaarMap[w.id] = false;
        }
      }
      setAadhaarByWorker(aadhaarMap);
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

  const [reviewingWorker, setReviewingWorker] = useState<Worker | null>(null);
  const [reviewDocs, setReviewDocs] = useState<WorkerDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [verifyingDoc, setVerifyingDoc] = useState<number | null>(null);

  const reviewDocuments = async (w: Worker) => {
    setReviewingWorker(w);
    setLoadingDocs(true);
    try {
      setReviewDocs(await api.workers.documents.list(w.id));
    } catch (e) {
      alert(errorMessage(e));
      setReviewDocs([]);
    } finally {
      setLoadingDocs(false);
    }
  };

  const verifyDocument = async (docId: number, verified: boolean) => {
    if (!reviewingWorker) return;
    setVerifyingDoc(docId);
    try {
      const reason = verified ? undefined : window.prompt("Reason for rejection (optional):", "") ?? undefined;
      await api.workers.documents.verify(docId, { verified, rejection_reason: reason });
      await load();
    } catch (e) {
      alert(errorMessage(e));
    } finally {
      setVerifyingDoc(null);
    }
  };

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
      if (reviewingWorker?.id === id) setReviewingWorker(null);
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
                <span className="small">
                  {aadhaarByWorker[w.id] ? "✓ Aadhaar verified" : "✗ Aadhaar not verified"}
                </span>
                <div className="row" style={{ justifyContent: "flex-end", gap: 6 }}>
                  <button className="chip" onClick={() => reviewDocuments(w)} disabled={loading} title="Review uploaded documents">
                    Review documents
                  </button>
                  <button className="chip on" onClick={() => approve(w.id)} disabled={loading} title="Approve Worker Directly">
                    <Check /> Approve
                  </button>
                  <button className="chip off" onClick={() => reject(w.id)} disabled={loading} title="Reject">
                    <Cross />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {reviewingWorker && (
        <div className="modal-backdrop" onClick={() => setReviewingWorker(null)}>
          <div className="card stack" style={{ width: "min(560px, 92vw)", margin: "24px auto", maxHeight: "80vh", overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div className="row between" style={{ alignItems: "flex-start" }}>
              <div className="stack" style={{ gap: 2 }}>
                <h2 style={{ margin: 0 }}>{reviewingWorker.name}</h2>
                <div className="small muted">{titleCase(reviewingWorker.trade)} · {reviewingWorker.phone ?? "no phone"}</div>
              </div>
              <button className="back" onClick={() => setReviewingWorker(null)} aria-label="Close">✕</button>
            </div>
            <p className="small muted" style={{ margin: "4px 0 12px" }}>
              The worker uploaded these documents. Review each document or approve the worker profile directly.
            </p>
            {verifyingDoc !== null && <div className="small muted">Saving…</div>}
            {loadingDocs && <div className="small muted">Loading documents…</div>}
            <div className="stack" style={{ gap: 8 }}>
              {reviewDocs.length === 0 ? (
                <div className="notice info small">
                  No documents uploaded yet by this worker. You can still approve them directly using the button below.
                </div>
              ) : (
                reviewDocs.map((d) => (
                  <div className="row between" style={{ gap: 12, flexWrap: "wrap", padding: "8px 0", borderTop: "1px solid var(--line)" }} key={d.id}>
                    <div className="stack grow" style={{ gap: 2 }}>
                      <span style={{ fontWeight: 700 }}>{d.document_type}</span>
                      <a href={d.file_url} target="_blank" rel="noreferrer" className="small" style={{ wordBreak: "break-all" }}>
                        {d.file_url}
                      </a>
                      {d.verified ? (
                        <span className="small" style={{ color: "var(--green-d)" }}>✓ verified{d.verified_at ? ` · ${new Date(d.verified_at.replace(" ", "T") + "Z").toLocaleString("en-IN")}` : ""}</span>
                      ) : d.rejection_reason ? (
                        <span className="small" style={{ color: "var(--red)" }}>✗ rejected: {d.rejection_reason}</span>
                      ) : (
                        <span className="small muted">✗ not yet reviewed</span>
                      )}
                    </div>
                    <div className="row" style={{ gap: 6 }}>
                      {d.verified ? (
                        <button className="chip off" onClick={() => verifyDocument(d.id, false)} disabled={verifyingDoc === d.id} title="Unverify / re-open">Unverify</button>
                      ) : (
                        <button className="chip on" onClick={() => verifyDocument(d.id, true)} disabled={verifyingDoc === d.id} title="Mark verified"><Check /></button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="row" style={{ justifyContent: "space-between", gap: 8, marginTop: 16 }}>
              <button
                type="button"
                className="btn primary small"
                onClick={() => approve(reviewingWorker.id)}
                disabled={loading}
              >
                ✓ Approve Worker Account Now
              </button>
              <button className="btn outline small" onClick={() => setReviewingWorker(null)}>Close</button>
            </div>
          </div>
        </div>
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
