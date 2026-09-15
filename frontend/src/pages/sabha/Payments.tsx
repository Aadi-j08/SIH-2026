/**
 * Payments: how money works in the cooperative — the community rate card the
 * general body fixed, the prices being agreed right now, and the 85/10/5 split
 * of every finished job. No money moves through the platform: a household pays
 * its worker directly and the ledger records the agreed amount.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage, formatRupees, titleCase, type Dashboard, type Rate, type RateUpdate, type Settlement } from "../../api";
import { Check, Scale } from "../../components/Icons";
import { useSabha } from "../../components/SabhaShell";
import { MoneySplit } from "./Demands";

function ago(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso.replace(" ", "T") + "Z").getTime()) / 60000));
  if (mins < 60) return `${mins} min ago`;
  if (mins < 60 * 24) return `${Math.floor(mins / 60)} h ago`;
  return `${Math.floor(mins / 1440)} d ago`;
}

const STATUS: Record<Settlement["status"], { text: string; cls: string }> = {
  proposed: { text: "Waiting on customer", cls: "amber" },
  countered: { text: "Waiting on worker", cls: "amber" },
  disputed: { text: "Sabha to decide", cls: "terracotta" },
  agreed: { text: "Agreed", cls: "green" },
};

export default function Payments() {
  const { reload } = useSabha();
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [rates, setRates] = useState<Rate[] | null>(null);
  const [settlements, setSettlements] = useState<Settlement[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    Promise.all([api.admin.dashboard(), api.rates.list(), api.settlement.list()])
      .then(([d, r, s]) => {
        setDash(d);
        setRates(r);
        setSettlements(s);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));

  useEffect(() => {
    void load();
  }, []);

  const open = (settlements ?? []).filter((s) => s.status !== "agreed");
  const recent = (settlements ?? []).filter((s) => s.status === "agreed").slice(0, 6);
  const workers = (dash?.workers ?? []).filter((w) => w.completed_jobs > 0).sort((a, b) => b.earnings_rupees - a.earnings_rupees);

  return (
    <div className="page wide sabha-page">
      <div className="stack" style={{ gap: 4 }}>
        <h1 style={{ fontSize: 28 }}>Payments</h1>
        <div className="sub">A community rate, a price both sides agree, paid hand to hand — the ledger only keeps the record</div>
      </div>
      {error && <div className="notice error">{error}</div>}
      {dash && (
        <div className="metrics four">
          <div className="metric"><div className="label">Agreed to date</div><div className="value num">{formatRupees(dash.money.gross_rupees)}</div><div className="caption">across {dash.bookings.completed} completed jobs</div></div>
          <div className="metric"><div className="label">Earned by members</div><div className="value num" style={{ color: "var(--green-d)" }}>{formatRupees(dash.money.worker_payouts_rupees)}</div><div className="caption">85% · paid to them directly</div></div>
          <div className="metric"><div className="label">Cooperative fund</div><div className="value num">{formatRupees(dash.money.welfare_fund_rupees)}</div><div className="caption">10% · members' contribution</div></div>
          <div className="metric"><div className="label">Prices open now</div><div className="value num" style={{ color: open.length ? "var(--terracotta-d)" : undefined }}>{open.length}</div><div className="caption">{open.filter((s) => s.status === "disputed").length} for the Sabha to decide</div></div>
        </div>
      )}

      <div className="sabha-grid">
        {rates && <RateCard rates={rates} onSaved={async () => { await load(); await reload(); }} />}
        <section className="panel" aria-labelledby="open-h">
          <div className="stack" style={{ gap: 2 }}>
            <h2 id="open-h">Prices being agreed</h2>
            <div className="small muted">What each side has put on the table, and whose turn it is</div>
          </div>
          {settlements === null ? (
            <div className="small muted">Loading…</div>
          ) : open.length === 0 ? (
            <div className="small muted">Nothing open. Every finished job has an agreed price.</div>
          ) : (
            <div className="stack">
              {open.map((s) => (
                <div className="dispute" key={s.id}>
                  <div className="stack grow" style={{ gap: 2 }}>
                    <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 700 }}>#{s.booking_id} · {titleCase(s.trade)}</span>
                      <span className={`pill ${STATUS[s.status].cls}`}>{STATUS[s.status].text}</span>
                    </div>
                    <div className="tiny muted">
                      {s.worker_name} proposed {formatRupees(s.proposed_rupees)}
                      {s.counter_rupees !== null ? ` · ${s.customer_name} offered ${formatRupees(s.counter_rupees)}` : ""}
                      {` · card ${formatRupees(s.standard_rupees)} (${s.hours_worked} h) · ${ago(s.responded_at ?? s.created_at)}`}
                    </div>
                  </div>
                  {s.status === "disputed" ? (
                    <Link to={`/sabha/disputes#d${s.dispute_id}`} className="btn small primary"><Scale size={14} />Decide</Link>
                  ) : (
                    <span className="tiny muted hide-narrow">nudged automatically after 24 h</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {recent.length > 0 && (
            <>
              <div className="label" style={{ marginTop: 6 }}>Recently agreed</div>
              <div className="table">
                {recent.map((s) => (
                  <div className="trow t4" key={s.id}>
                    <span style={{ fontWeight: 700 }}>#{s.booking_id} {titleCase(s.trade)}</span>
                    <span className="small muted">{s.worker_name}</span>
                    <span className="num" style={{ fontWeight: 700 }}>{formatRupees(s.agreed_rupees ?? 0)}</span>
                    <span className="small muted hide-narrow">
                      {s.dispute_id ? "Sabha decided" : s.counter_rupees !== null ? "after a counter" : "first offer"}{s.paid_via ? ` · ${s.paid_via.toUpperCase()}` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>

      {dash && (
        <div className="sabha-grid">
          <div className="panel">
            <div className="stack" style={{ gap: 2 }}>
              <h2>The split</h2>
              <div className="small muted">Fixed by the general body; the ledger applies it to every agreed amount</div>
            </div>
            <MoneySplit dashboard={dash} />
            <div className="tiny muted">The household pays the member in full, directly. The member's 15% (fund + running costs) is settled at the weekly Sabha, in the open, against this ledger.</div>
          </div>
          <div className="panel">
            <div className="stack" style={{ gap: 2 }}>
              <h2>Earnings by member</h2>
              <div className="small muted">Completed jobs, earnings and days of engagement toward benefits</div>
            </div>
            <div className="table">
              <div className="trow head t4">
                <span>Worker</span>
                <span>Jobs</span>
                <span>Earned</span>
                <span className="hide-narrow">Days</span>
              </div>
              {workers.map((w) => (
                <div className="trow t4" key={w.id}>
                  <span style={{ fontWeight: 700 }}>{w.name ?? `Worker ${w.id}`}</span>
                  <span className="num">{w.completed_jobs}</span>
                  <span className="num" style={{ fontWeight: 700 }}>{formatRupees(w.earnings_rupees)}</span>
                  <span className="num small muted hide-narrow">{w.engagement_days} / 90</span>
                </div>
              ))}
              {workers.length === 0 && <div className="small muted">No completed jobs yet.</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── the community rate card ──────────────────────────────────────────

function RateCard({ rates, onSaved }: { rates: Rate[]; onSaved: () => Promise<void> }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<RateUpdate>({});
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  const start = (r: Rate) => {
    setEditing(r.trade);
    setDraft({ visit_charge_rupees: r.visit_charge_rupees, hourly_rate_rupees: r.hourly_rate_rupees, min_hours: r.min_hours, band_percent: r.band_percent, note: r.note ?? "" });
    setNote(null);
  };
  const save = async () => {
    if (!editing) return;
    setBusy(true);
    try {
      await api.rates.update(editing, { ...draft, note: draft.note || null } as RateUpdate);
      setEditing(null);
      setNote({ kind: "info", text: `${titleCase(editing)} rate updated. New quotes use it from now; prices already on the table keep the old card.` });
      await onSaved();
    } catch (e) {
      setNote({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const num = (key: keyof RateUpdate, label: string, step = 1) => (
    <label className="stack" style={{ gap: 2 }} key={key}>
      <span className="tiny muted">{label}</span>
      <span className="field" style={{ minHeight: 36 }}>
        <input type="number" step={step} min={0} value={(draft[key] as number | undefined) ?? ""} onChange={(e) => setDraft({ ...draft, [key]: e.target.value === "" ? undefined : Number(e.target.value) })} style={{ height: 32, width: 90 }} />
      </span>
    </label>
  );

  return (
    <section className="panel" aria-labelledby="rates-h">
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="stack" style={{ gap: 2 }}>
          <h2 id="rates-h">Community rate card</h2>
          <div className="small muted">What an hour of each trade is worth, fixed by the general body. Every price starts here; the two sides may agree within the band.</div>
        </div>
        <span className="pill green"><Check size={12} strokeWidth={3} />Set by members</span>
      </div>
      {note && <div className={`notice ${note.kind}`}>{note.text}</div>}
      <div className="table">
        <div className="trow head t4">
          <span>Service</span>
          <span>Visit</span>
          <span>Per hour</span>
          <span>Band</span>
        </div>
        {rates.map((r) =>
          editing === r.trade ? (
            <div className="stack" key={r.trade} style={{ padding: "8px 0", gap: 8 }}>
              <div style={{ fontWeight: 700 }}>{titleCase(r.trade)}</div>
              <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
                {num("visit_charge_rupees", "Visit ₹", 10)}
                {num("hourly_rate_rupees", "Per hour ₹", 10)}
                {num("min_hours", "Min hours", 0.5)}
                {num("band_percent", "Band %", 5)}
              </div>
              <label className="field" style={{ minHeight: 36 }}>
                <input value={draft.note ?? ""} onChange={(e) => setDraft({ ...draft, note: e.target.value })} placeholder="Resolution reference, e.g. General body, 4 Sept 2026" style={{ height: 32 }} />
              </label>
              <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
                <button type="button" className="btn small outline" onClick={() => setEditing(null)} disabled={busy}>Cancel</button>
                <button type="button" className="btn small primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save rate"}</button>
              </div>
            </div>
          ) : (
            <button type="button" className="trow t4 rate-row" key={r.trade} onClick={() => start(r)} title={r.note ?? "Tap to edit"}>
              <span style={{ fontWeight: 700 }}>
                {titleCase(r.trade)}
                {r.typical_hours && <span className="tiny muted"> · ~{r.typical_hours} h</span>}
              </span>
              <span className="num">{formatRupees(r.visit_charge_rupees)}</span>
              <span className="num">{formatRupees(r.hourly_rate_rupees)}<span className="tiny muted"> · min {r.min_hours} h</span></span>
              <span className="num">±{r.band_percent}%</span>
            </button>
          ),
        )}
      </div>
      <div className="tiny muted">Tap a row to change it after a general-body resolution. Households see the card before booking; workers see it on every job.</div>
    </section>
  );
}
