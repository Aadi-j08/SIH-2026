import { useEffect, useState } from "react";

import { api, errorMessage, formatRupees, formatWhen, titleCase, type DeclineReason, type Settlement, type WorkerJob } from "../api";
import { Check, MapPin } from "./Icons";
import { ProposePrice, RateHint, SettlementCard } from "./Settlement";

const REASONS: { id: DeclineReason; label: string }[] = [
  { id: "unwell", label: "Not well today" },
  { id: "too_far", label: "Too far" },
  { id: "already_booked", label: "Already booked" },
  { id: "not_my_job", label: "Not my kind of job" },
];

function whyYou(explanation: string | null): string | null {
  if (!explanation) return null;
  const part = explanation.split(";")[1]?.trim().replace(/\s*\(.*\)/, "");
  return part || "engine’s top pick";
}

function Phone(p: { size?: number }) {
  return (
    <svg width={p.size ?? 20} height={p.size ?? 20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" />
    </svg>
  );
}

/**
 * One assigned job, in its states: waiting for a reply (Accept / Can’t do it),
 * accepted (call, directions, Job done → propose the price), the price on the
 * table (waiting on the customer / their counter to answer), and the decline
 * reason sheet in between. The price is never typed as a bill: it comes from
 * the community rate card and both sides agree it.
 */
export default function JobCard({ job, onChange }: { job: WorkerJob; onChange: () => Promise<void> | void }) {
  const [mode, setMode] = useState<"view" | "decline" | "price">("view");
  const [reason, setReason] = useState<DeclineReason | null>(null);
  const [busyToday, setBusyToday] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const [settlement, setSettlement] = useState<Settlement | null>(null);
  const [settlementError, setSettlementError] = useState(false);

  // the job list carries a brief; the full record (band, note, ledger) comes from its own endpoint
  const brief = job.settlement;
  useEffect(() => {
    if (!brief) {
      setSettlement(null);
      setSettlementError(false);
      return;
    }
    let alive = true;
    setSettlementError(false);
    api.settlement.get(job.booking_id).then((s) => {
      if (!alive) return;
      if (s) {
        setSettlement(s);
      } else {
        // API returned null — the settlement record is missing or invalid
        setSettlementError(true);
      }
    }).catch(() => { if (alive) setSettlementError(true); });
    return () => {
      alive = false;
    };
  }, [job.booking_id, brief?.status, brief?.counter_rupees]);

  const run = async (fn: () => Promise<unknown>, done?: string) => {
    setBusy(true);
    setMessage(null);
    try {
      await fn();
      if (done) setMessage({ kind: "info", text: done });
      await onChange();
    } catch (e) {
      setMessage({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  const accept = () => run(() => api.kaam.accept(job.booking_id));
  const decline = () =>
    reason &&
    run(async () => {
      const result = await api.kaam.decline(job.booking_id, reason, busyToday);
      setMode("view");
      setMessage({
        kind: "info",
        text: result.reassigned_to ? `Passed on to ${result.reassigned_to}. No penalty.` : "Passed back to the council. No penalty.",
      });
    });
  const isNew = job.outcome === "assigned";
  const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${job.latitude},${job.longitude}`;

  if (mode === "price") {
    return (
      <ProposePrice
        bookingId={job.booking_id}
        trade={job.trade}
        onCancel={() => setMode("view")}
        onDone={async (s) => {
          setSettlement(s);
          setMode("view");
          setMessage({ kind: "info", text: `${formatRupees(s.proposed_rupees)} proposed. ${job.customer_name.split(" ")[0]} will see it now.` });
          await onChange();
        }}
      />
    );
  }

  if (mode === "decline") {
    return (
      <div className="sheet">
        <div className="stack" style={{ gap: 2 }}>
          <div className="display" style={{ fontSize: 18, fontWeight: 700 }}>Why not this one?</div>
          <div className="hi small muted">क्यों नहीं? — इससे इंजन को अगली बार बेहतर चुनने में मदद मिलती है</div>
        </div>
        <div className="reason-grid">
          {REASONS.map((r) => (
            <button key={r.id} type="button" className={reason === r.id ? "active" : ""} onClick={() => setReason(r.id)}>
              {r.label}
            </button>
          ))}
        </div>
        <label className="row small muted" style={{ gap: 8 }}>
          <input type="checkbox" checked={busyToday} onChange={(e) => setBusyToday(e.target.checked)} />
          Also mark me busy for the rest of today
        </label>
        {message && <div className={`notice ${message.kind}`}>{message.text}</div>}
        <div className="row" style={{ gap: 8 }}>
          <button type="button" className="btn dark grow" onClick={decline} disabled={busy || !reason}>
            {busy ? "Passing on…" : "Pass it on"}
          </button>
          <button type="button" className="btn outline" onClick={() => setMode("view")} disabled={busy}>
            Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`job-card${isNew ? " new" : ""}`}>
      <div className="row between" style={{ alignItems: "flex-start", gap: 10 }}>
        {isNew ? (
          <div className="row" style={{ gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--green-d)", display: "inline-block" }} />
            <span className="label" style={{ color: "var(--green-d)" }}>New job · reply please</span>
          </div>
        ) : (
          <span className="label">Today’s job</span>
        )}
        {isNew ? (
          <span className="hi small muted">नया काम</span>
        ) : (
          <span className="pill green"><Check size={12} strokeWidth={3} />Accepted</span>
        )}
      </div>
      <div className="stack" style={{ gap: 3 }}>
        <div className="display" style={{ fontSize: 17, fontWeight: 700 }}>
          {job.customer_name} · {titleCase(job.trade)}
        </div>
        <div className="small muted">
          {formatWhen(job.scheduled_for)}
          {job.address ? ` · ${job.address}` : ""}
        </div>
        {whyYou(job.explanation) && <span className="pill green" style={{ alignSelf: "flex-start" }}>Why you: {whyYou(job.explanation)}</span>}
      </div>

      {message && <div className={`notice ${message.kind}`}>{message.text}</div>}

      {isNew ? (
        <>
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn green grow" onClick={accept} disabled={busy}>
              Accept · हाँ
            </button>
            <button type="button" className="btn outline" onClick={() => setMode("decline")} disabled={busy}>
              Can’t do it
            </button>
          </div>
          <div className="tiny muted">If you can’t, the job goes to the next worker at once. Passing on never counts against you.</div>
        </>
      ) : (
        <>
          <div className="job-actions">
            <a href={job.customer_phone ? `tel:${job.customer_phone}` : undefined} className={job.customer_phone ? "" : "disabled"}>
              <Phone />
              {job.customer_phone ? `Call ${job.customer_name.split(" ")[0]}` : "No number"}
            </a>
            <a href={mapsUrl} target="_blank" rel="noreferrer">
              <MapPin size={20} />
              Directions
            </a>
            <button type="button" onClick={() => setMode("decline")} disabled={busy}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
              Can’t make it
            </button>
          </div>
          <div className="divider" />
          {settlement ? (
            <SettlementCard settlement={settlement} role="worker" onChange={async () => { setSettlement(await api.settlement.get(job.booking_id)); await onChange(); }} />
          ) : brief && !settlementError ? (
            <div className="small muted">Loading the price on the table…</div>
          ) : (
            <div className="stack" style={{ gap: 6 }}>
              {settlementError && <div className="notice error">Could not load the settlement details. You can try proposing the price again.</div>}
              <div className="label">When finished</div>
              <button type="button" className="btn green" style={{ minHeight: 50 }} disabled={busy} onClick={() => setMode("price")}>
                <Check size={18} />
                Job done · propose the price
              </button>
              <RateHint trade={job.trade} compact />
              <div className="tiny muted">You say the hours and materials; the community rate prices it; the customer agrees. You keep 85%, paid to you directly.</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
