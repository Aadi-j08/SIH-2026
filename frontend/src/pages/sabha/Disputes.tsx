/** Resolution centre: the cooperative as neutral mediator between a household and a member. */
import { useEffect, useState } from "react";

import { api, errorMessage, formatRupees, titleCase, type Dispute } from "../../api";
import { Check, Scale } from "../../components/Icons";
import { useSabha } from "../../components/SabhaShell";

function when(iso: string): string {
  return new Date(iso.replace(" ", "T") + "Z").toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function Disputes() {
  const { reload } = useSabha();
  const [rows, setRows] = useState<Dispute[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [tab, setTab] = useState<"open" | "resolved">("open");
  const [amounts, setAmounts] = useState<Record<number, string>>({});

  const load = () => api.disputes.list().then(setRows).catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    void load();
  }, []);

  const resolve = async (id: number) => {
    const text = (notes[id] ?? "").trim();
    if (!text) {
      setError(`#${id}: write the resolution first.`);
      return;
    }
    setBusy(id);
    setError(null);
    try {
      await api.disputes.resolve(id, text);
      await Promise.all([load(), reload()]);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  // a price dispute: the council fixes the amount, which completes the job and closes the dispute in one step
  const decide = async (d: Dispute) => {
    const text = (notes[d.id] ?? "").trim();
    const amount = Number(amounts[d.id] ?? d.settlement_standard_rupees ?? 0);
    if (!text || !(amount > 0)) {
      setError(`#${d.id}: set the amount and write the resolution first.`);
      return;
    }
    setBusy(d.id);
    setError(null);
    try {
      await api.settlement.resolve(d.booking_id, amount, text);
      await Promise.all([load(), reload()]);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const open = (rows ?? []).filter((d) => d.status === "open");
  const resolved = (rows ?? []).filter((d) => d.status === "resolved");
  const rate = rows && rows.length ? Math.round((resolved.length / rows.length) * 100) : null;
  const shown = tab === "open" ? open : resolved;

  return (
    <div className="page wide sabha-page">
      <div className="row between" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div className="stack" style={{ gap: 4 }}>
          <div className="row" style={{ gap: 8 }}>
            <Scale size={24} style={{ color: "var(--indigo-d)" }} />
            <h1 style={{ fontSize: 28 }}>Resolution centre</h1>
          </div>
          <div className="sub">{rows ? `${open.length} Open · ${resolved.length} Resolved · ${rate === null ? "—" : `${rate}% resolution rate`}` : "Loading…"}</div>
        </div>
        <div className="seg">
          <a role="tab" aria-selected={tab === "open"} className={tab === "open" ? "active" : undefined} onClick={() => setTab("open")} style={{ cursor: "pointer" }}>Open ({open.length})</a>
          <a role="tab" aria-selected={tab === "resolved"} className={tab === "resolved" ? "active" : undefined} onClick={() => setTab("resolved")} style={{ cursor: "pointer" }}>Resolved ({resolved.length})</a>
        </div>
      </div>
      {error && <div className="notice error">{error}</div>}
      <div className="stack">
        {shown.map((d) => (
          <div className="panel" key={d.id} id={`d${d.id}`}>
            <div className="row between" style={{ alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
              <div className="stack" style={{ gap: 4 }}>
                <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                  <span className="display" style={{ fontSize: 17, fontWeight: 700 }}>#{d.id} {d.label}</span>
                  <span className={`pill ${d.kind === "payment" ? "indigo" : d.kind === "quality" ? "terracotta" : "grey"}`}>{titleCase(d.kind)}</span>
                  {d.amount_rupees !== null && <span className="pill grey">{formatRupees(d.amount_rupees)}</span>}
                </div>
                <div className="small muted">
                  Booking #{d.booking_id}{d.trade ? ` · ${titleCase(d.trade)}` : ""} · {d.customer_name ?? "Household"}
                  {" "}{d.raised_by === "customer" ? "→" : "←"}{" "}{d.worker_name ?? "Worker"} · raised by {d.raised_by === "council" ? "the council" : d.raised_by_name ?? d.raised_by} on {when(d.created_at)}
                </div>
                {d.description && <div className="small" style={{ lineHeight: 1.5 }}>“{d.description}”</div>}
                {d.settlement_status === "agreed" && d.amount_rupees === null && (
                  <span className="pill grey" style={{ alignSelf: "flex-start" }}>Price agreed {formatRupees(d.settlement_proposed_rupees ?? 0)}</span>
                )}
                {d.settlement_status && d.settlement_status !== "agreed" && (
                  <div className="row small" style={{ gap: 10, flexWrap: "wrap" }}>
                    <span className="pill grey">Rate card {formatRupees(d.settlement_standard_rupees ?? 0)}</span>
                    <span className="pill green">Worker proposed {formatRupees(d.settlement_proposed_rupees ?? 0)}</span>
                    {d.settlement_counter_rupees !== null && <span className="pill terracotta">Customer offered {formatRupees(d.settlement_counter_rupees)}</span>}
                  </div>
                )}
              </div>
              {d.status === "resolved" && (
                <span className="pill green" style={{ gap: 5 }}>
                  <Check size={13} /> Resolved {d.resolved_at ? when(d.resolved_at) : ""}
                </span>
              )}
            </div>
            {d.status === "open" && d.settlement_status === "disputed" ? (
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <label className="field" style={{ minHeight: 40, width: 140 }}>
                  <span className="muted">₹</span>
                  <input inputMode="decimal" value={amounts[d.id] ?? String(d.settlement_standard_rupees ?? "")} onChange={(e) => setAmounts((a) => ({ ...a, [d.id]: e.target.value }))} aria-label="Amount the Sabha fixes" style={{ height: 36, textAlign: "right" }} />
                </label>
                <label className="field grow" style={{ minHeight: 40, minWidth: 240 }}>
                  <input value={notes[d.id] ?? ""} onChange={(e) => setNotes((n) => ({ ...n, [d.id]: e.target.value }))} placeholder="Why this amount — both sides will read it" aria-label="Resolution" style={{ height: 36 }} />
                </label>
                <button type="button" className="btn small primary" disabled={busy === d.id} onClick={() => void decide(d)}>
                  {busy === d.id ? "Saving…" : "Fix the price & close"}
                </button>
              </div>
            ) : d.status === "open" ? (
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <label className="field grow" style={{ minHeight: 40, minWidth: 240 }}>
                  <input value={notes[d.id] ?? ""} onChange={(e) => setNotes((n) => ({ ...n, [d.id]: e.target.value }))} placeholder="Resolution, in one line — e.g. bill corrected to the quoted amount" aria-label="Resolution" style={{ height: 36 }} />
                </label>
                <button type="button" className="btn small primary" disabled={busy === d.id} onClick={() => void resolve(d.id)}>
                  {busy === d.id ? "Saving…" : d.kind === "quality" ? "Record investigation" : "Mark resolved"}
                </button>
              </div>
            ) : (
              <div className="notice info small">Resolution: {d.resolution}</div>
            )}
          </div>
        ))}
        {rows && shown.length === 0 && <div className="panel small muted">{tab === "open" ? "No open disputes. The cooperative is at peace." : "Nothing resolved yet."}</div>}
      </div>
    </div>
  );
}
