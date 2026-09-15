/**
 * The price of a job, agreed by both sides.
 *
 *   RateHint      what the community rate card says a trade costs (Ghar before booking, Kaam on a job)
 *   ProposePrice  the worker's "job done" sheet: hours + materials → the card prices it → propose
 *   SettlementCard the running agreement: what is on the table, whose turn, agree / counter / ask Sabha,
 *                 and once agreed the split and "paid directly to the worker"
 *
 * Nothing here moves money. The customer pays the worker in hand or by UPI;
 * the platform records only the amount the two agreed.
 */
import { useEffect, useState } from "react";

import { api, errorMessage, formatRupees, titleCase, type LedgerEntry, type PaidVia, type Quote, type Rate, type Settlement } from "../api";
import { Check, Scale } from "./Icons";

const PARTY_LABEL: Record<LedgerEntry["party"], string> = { worker: "To the worker", welfare_fund: "Workers' welfare fund", platform_operations: "Platform operations" };
const RAMP = ["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)"];

export function rateLine(r: Rate): string {
  return `${formatRupees(r.visit_charge_rupees)} visit + ${formatRupees(r.hourly_rate_rupees)}/hour · min ${r.min_hours} h`;
}

// ── rate hint ────────────────────────────────────────────────────────

export function RateHint({ trade, compact }: { trade: string; compact?: boolean }) {
  const [rate, setRate] = useState<Rate | null>(null);
  useEffect(() => {
    let alive = true;
    api.rates.list().then((rs) => alive && setRate(rs.find((r) => r.trade === trade) ?? null)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [trade]);
  if (!rate) return null;
  const typical = rate.typical_hours ?? rate.min_hours;
  const typicalAmount = rate.visit_charge_rupees + Math.max(typical, rate.min_hours) * rate.hourly_rate_rupees;
  if (compact) {
    return <span className="tiny muted">Community rate: {rateLine(rate)}</span>;
  }
  return (
    <div className="card soft stack" style={{ gap: 4 }}>
      <div className="row between" style={{ gap: 8 }}>
        <div style={{ fontWeight: 700 }}>Community rate for {titleCase(trade)}</div>
        <span className="pill green">Set by the general body</span>
      </div>
      <div className="small">{rateLine(rate)}</div>
      <div className="tiny muted">
        A typical job ({typical} h) comes to about {formatRupees(typicalAmount)} plus materials. You settle the final amount with the worker when the job ends and pay them directly — nothing is charged here.
      </div>
    </div>
  );
}

// ── the worker's "job done" sheet ────────────────────────────────────

function Stepper({ value, onChange, step = 0.5, min = 0.5, max = 24, unit }: { value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number; unit: string }) {
  const set = (v: number) => onChange(Math.min(max, Math.max(min, Math.round(v * 2) / 2)));
  return (
    <div className="row" style={{ gap: 6 }}>
      <button type="button" className="btn outline" style={{ minWidth: 48, minHeight: 48 }} onClick={() => set(value - step)} aria-label="Less">
        −
      </button>
      <div className="display num" style={{ minWidth: 76, textAlign: "center", fontSize: 22, fontWeight: 700 }}>
        {value} <small className="muted" style={{ fontSize: 14, fontWeight: 500 }}>{unit}</small>
      </div>
      <button type="button" className="btn outline" style={{ minWidth: 48, minHeight: 48 }} onClick={() => set(value + step)} aria-label="More">
        +
      </button>
    </div>
  );
}

export function ProposePrice({ bookingId, trade, onDone, onCancel }: { bookingId: number; trade: string; onDone: (s: Settlement) => void; onCancel: () => void }) {
  const [hours, setHours] = useState(1);
  const [materials, setMaterials] = useState("");
  const [note, setNote] = useState("");
  const [amount, setAmount] = useState<string>("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const materialsValue = Number(materials) || 0;
  useEffect(() => {
    let alive = true;
    api.rates.quote(trade, hours, materialsValue).then((q) => {
      if (!alive) return;
      setQuote(q);
      if (q.typical_hours && hours === 1 && q.typical_hours !== 1) setHours(q.typical_hours);
    }).catch((e) => alive && setError(errorMessage(e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trade, hours, materialsValue]);

  const finalAmount = amount === "" ? quote?.standard_rupees ?? 0 : Number(amount);
  const inBand = quote ? finalAmount >= quote.min_fair_rupees && finalAmount <= quote.max_fair_rupees : true;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await api.settlement.propose(bookingId, {
        hours_worked: hours,
        materials_rupees: materialsValue,
        work_note: note.trim() || null,
        amount_rupees: amount === "" ? null : Number(amount),
      });
      onDone(s);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sheet">
      <div className="stack" style={{ gap: 2 }}>
        <div className="display" style={{ fontSize: 18, fontWeight: 700 }}>Job done — what did it take?</div>
        <div className="hi small muted">काम हो गया — कितना समय लगा? दाम समुदाय की दर से बनेगा</div>
      </div>

      <div className="stack" style={{ gap: 6 }}>
        <div className="label">Time on the job</div>
        <Stepper value={hours} onChange={(v) => { setHours(v); setAmount(""); }} unit="hours" />
        {quote?.typical_hours && <div className="tiny muted">Most {trade} jobs this month took about {quote.typical_hours} h.</div>}
      </div>

      <div className="stack" style={{ gap: 6 }}>
        <div className="label">Materials you bought (at cost)</div>
        <label className="field" style={{ minHeight: 48 }}>
          <span className="muted">₹</span>
          <input inputMode="decimal" value={materials} onChange={(e) => { setMaterials(e.target.value); setAmount(""); }} placeholder="0" aria-label="Materials in rupees" style={{ height: 44 }} />
        </label>
      </div>

      <div className="stack" style={{ gap: 6 }}>
        <div className="label">What you did</div>
        <label className="field" style={{ minHeight: 48 }}>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. replaced the tap washer, checked the pipe" maxLength={300} style={{ height: 44 }} />
        </label>
      </div>

      {quote && (
        <div className="card soft stack" style={{ gap: 6 }}>
          <div className="row between">
            <span className="small" style={{ fontWeight: 700 }}>Community rate says</span>
            <span className="display num" style={{ fontSize: 22, fontWeight: 700 }}>{formatRupees(quote.standard_rupees)}</span>
          </div>
          <div className="tiny muted">{quote.explanation}</div>
          <div className="divider" />
          <div className="row" style={{ gap: 8, alignItems: "center" }}>
            <span className="small grow">Propose a different amount (fair band {formatRupees(quote.min_fair_rupees)}–{formatRupees(quote.max_fair_rupees)})</span>
            <label className="field" style={{ minHeight: 44, width: 130 }}>
              <span className="muted">₹</span>
              <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={String(quote.standard_rupees)} aria-label="Proposed amount" style={{ height: 40, textAlign: "right" }} />
            </label>
          </div>
          {!inBand && <div className="notice error">Outside the fair band the community set. Propose within it, or the Sabha will need to decide.</div>}
        </div>
      )}

      {error && <div className="notice error">{error}</div>}
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="btn green grow" style={{ minHeight: 50 }} disabled={busy || !quote || !inBand} onClick={submit}>
          {busy ? "Sending…" : `Propose ${formatRupees(finalAmount)} to the customer`}
        </button>
        <button type="button" className="btn outline" onClick={onCancel} disabled={busy}>
          Back
        </button>
      </div>
      <div className="tiny muted">The customer agrees, suggests a different amount, or asks the Sabha. Once agreed you keep 85% — they pay you directly, cash or UPI.</div>
    </div>
  );
}

// ── the running agreement ────────────────────────────────────────────

const PAID_VIA: { id: PaidVia; label: string }[] = [
  { id: "upi", label: "UPI" },
  { id: "cash", label: "Cash" },
  { id: "other", label: "Other" },
];

export function SettlementCard({ settlement: s, role, onChange }: { settlement: Settlement; role: "customer" | "worker" | "council"; onChange: () => Promise<void> | void }) {
  const [mode, setMode] = useState<"view" | "counter" | "dispute">("view");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [paidVia, setPaidVia] = useState<PaidVia>("upi");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onTable = s.status === "countered" ? s.counter_rupees ?? s.proposed_rupees : s.proposed_rupees;
  const myTurn = s.waiting_on === role;
  const otherSide = role === "customer" ? s.worker_name ?? "the worker" : s.customer_name ?? "the customer";

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setMode("view");
      await onChange();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const agree = () => run(() => api.settlement.respond(s.booking_id, { action: "agree", paid_via: role === "customer" ? paidVia : null }));
  const counter = () => run(() => api.settlement.respond(s.booking_id, { action: "counter", amount_rupees: Number(amount), note: note.trim() || null }));
  const dispute = () => run(() => api.settlement.respond(s.booking_id, { action: "dispute", note: note.trim() || null }));

  // ── agreed ──
  if (s.status === "agreed") {
    const total = s.agreed_rupees ?? 0;
    return (
      <div className="card stack" style={{ gap: 8 }}>
        <div className="row between">
          <div className="row" style={{ gap: 8 }}>
            <span className="dot green"><Check size={16} /></span>
            <div style={{ fontWeight: 700 }}>Price agreed by both sides</div>
          </div>
          <div className="display num" style={{ fontSize: 22, fontWeight: 700 }}>{formatRupees(total)}</div>
        </div>
        <div className="tiny muted">
          {s.hours_worked} h of {s.trade}{s.materials_rupees ? ` + ${formatRupees(s.materials_rupees)} materials` : ""} · {s.explanation.split(";")[0]}
          {s.paid_via ? ` · paid ${s.paid_via === "upi" ? "by UPI" : s.paid_via === "cash" ? "in cash" : "directly"} to ${s.worker_name ?? "the worker"}` : " · paid directly to the worker"}
        </div>
        {s.ledger.length > 0 && (
          <>
            <div className="split">
              {s.ledger.map((e, i) => (
                <div key={e.party} style={{ width: `${e.share_percent}%`, background: RAMP[i] }} />
              ))}
            </div>
            {s.ledger.map((e, i) => (
              <div className="row small" key={e.party}>
                <span className="swatch" style={{ background: RAMP[i] }} />
                <span className="grow">{PARTY_LABEL[e.party]}</span>
                <span className="num" style={{ fontWeight: 700 }}>{formatRupees(e.amount_rupees)}</span>
                <span className="num muted" style={{ width: 36, textAlign: "right" }}>{e.share_percent}%</span>
              </div>
            ))}
            <div className="tiny muted">No money passes through SahakarSetu. The worker's 15% contribution to the cooperative is settled at the weekly Sabha, in the open.</div>
          </>
        )}
      </div>
    );
  }

  // ── disputed ──
  if (s.status === "disputed") {
    return (
      <div className="card stack" style={{ gap: 6 }}>
        <div className="row" style={{ gap: 8 }}>
          <Scale size={18} style={{ color: "var(--indigo-d)" }} />
          <div style={{ fontWeight: 700 }}>The Sabha is deciding the price</div>
        </div>
        <div className="small muted">
          {s.worker_name ?? "The worker"} proposed {formatRupees(s.proposed_rupees)}{s.counter_rupees ? `, ${s.customer_name ?? "the customer"} offered ${formatRupees(s.counter_rupees)}` : ""}. The council hears both sides and fixes an amount within the community's rate card.
        </div>
        {s.customer_note && <div className="tiny muted">“{s.customer_note}”</div>}
      </div>
    );
  }

  // ── counter / dispute sheets ──
  if (mode !== "view") {
    const counterValue = Number(amount);
    const inBand = counterValue >= s.min_fair_rupees && counterValue <= s.max_fair_rupees;
    return (
      <div className="sheet">
        <div className="display" style={{ fontSize: 18, fontWeight: 700 }}>{mode === "counter" ? "Suggest a different amount" : "Ask the Sabha to decide"}</div>
        {mode === "counter" && (
          <>
            <div className="small muted">The community's fair band for this job is {formatRupees(s.min_fair_rupees)}–{formatRupees(s.max_fair_rupees)} ({s.explanation.split(";")[0]}).</div>
            <label className="field" style={{ minHeight: 50 }}>
              <span className="muted">₹</span>
              <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Your amount" aria-label="Your amount" autoFocus style={{ height: 46 }} />
            </label>
            {amount !== "" && !inBand && <div className="notice error">Outside the fair band — pick an amount within it, or ask the Sabha.</div>}
          </>
        )}
        <label className="field" style={{ minHeight: 50 }}>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={mode === "counter" ? "Why? (optional)" : "What happened? The council will read this"} maxLength={300} style={{ height: 46 }} />
        </label>
        {error && <div className="notice error">{error}</div>}
        <div className="row" style={{ gap: 8 }}>
          <button type="button" className={`btn grow ${mode === "counter" ? "primary" : "dark"}`} disabled={busy || (mode === "counter" && !inBand)} onClick={mode === "counter" ? counter : dispute}>
            {busy ? "Sending…" : mode === "counter" ? `Offer ${amount ? formatRupees(counterValue) : "…"}` : "Send to the Sabha"}
          </button>
          <button type="button" className="btn outline" onClick={() => setMode("view")} disabled={busy}>Back</button>
        </div>
      </div>
    );
  }

  // ── proposed / countered ──
  return (
    <div className="card stack" style={{ gap: 8 }}>
      <div className="row between" style={{ alignItems: "flex-start", gap: 8 }}>
        <div className="stack" style={{ gap: 2 }}>
          <div style={{ fontWeight: 700 }}>
            {s.status === "proposed"
              ? role === "worker" ? "You proposed" : `${s.worker_name ?? "The worker"} proposes`
              : role === "customer" ? "You offered" : `${s.customer_name ?? "The customer"} offers`}
          </div>
          <div className="tiny muted">
            {s.hours_worked} h of {s.trade}{s.materials_rupees ? ` + ${formatRupees(s.materials_rupees)} materials` : ""} · rate card {formatRupees(s.standard_rupees)}
          </div>
        </div>
        <div className="display num" style={{ fontSize: 24, fontWeight: 700 }}>{formatRupees(onTable)}</div>
      </div>
      {s.work_note && <div className="small">“{s.work_note}”</div>}
      {s.status === "countered" && (
        <div className="small muted">
          Instead of the {formatRupees(s.proposed_rupees)} proposed{s.customer_note ? ` — “${s.customer_note}”` : ""}.
        </div>
      )}
      {error && <div className="notice error">{error}</div>}

      {myTurn ? (
        <>
          {role === "customer" && (
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              <span className="small muted">Paying by</span>
              {PAID_VIA.map((p) => (
                <button key={p.id} type="button" className={`chip${paidVia === p.id ? " on" : ""}`} style={{ minHeight: 36 }} onClick={() => setPaidVia(p.id)}>
                  {p.label}
                </button>
              ))}
            </div>
          )}
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button type="button" className={`btn grow ${role === "worker" ? "green" : "primary"}`} style={{ minHeight: 50 }} onClick={agree} disabled={busy}>
              <Check size={18} />
              {busy ? "Saving…" : `Agree ${formatRupees(onTable)}`}
            </button>
            {role === "customer" && (
              <button type="button" className="btn outline" style={{ minHeight: 50 }} onClick={() => setMode("counter")} disabled={busy}>
                Suggest different
              </button>
            )}
            <button type="button" className="btn outline" style={{ minHeight: 50 }} onClick={() => setMode("dispute")} disabled={busy}>
              Ask the Sabha
            </button>
          </div>
          <div className="tiny muted">
            {role === "customer"
              ? `Agree and pay ${s.worker_name ?? "the worker"} directly. 10% of the amount is the worker's contribution to the cooperative's welfare fund.`
              : "Accept the customer's offer, or ask the Sabha to decide. Either way you never pay to be heard."}
          </div>
        </>
      ) : (
        <div className="row small muted" style={{ gap: 8 }}>
          <span className="dot-mark" aria-hidden="true" style={{ background: "var(--terracotta)", width: 8, height: 8, borderRadius: 999, display: "inline-block" }} />
          Waiting for {otherSide} to reply. You'll see it here the moment they do.
        </div>
      )}
    </div>
  );
}
