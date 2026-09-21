import { useEffect, useState } from "react";

import { api, errorMessage, formatRupees, formatWhen, titleCase, type DeclineReason, type Settlement, type WorkerJob } from "../api";
import { AlertCircle, Camera, Check, MapPin } from "./Icons";
import { isSpeechSupported, speakJobSummary, stopSpeaking } from "../lib/speech";
import { ProposePrice, RateHint, SettlementCard } from "./Settlement";
import { PhotoProofModal, type PhotoProofMode } from "./PhotoProofModal";

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

function Volume2(p: { size?: number }) {
  return (
    <svg width={p.size ?? 18} height={p.size ?? 18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
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
  const [speaking, setSpeaking] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const [settlement, setSettlement] = useState<Settlement | null>(null);
  const [settlementError, setSettlementError] = useState(false);
  const [proofMode, setProofMode] = useState<PhotoProofMode | null>(null);

  useEffect(() => {
    return () => {
      stopSpeaking();
    };
  }, []);

  const toggleSpeak = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
    } else {
      setSpeaking(true);
      speakJobSummary(job, () => setSpeaking(false), () => setSpeaking(false));
    }
  };

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

  return (
    <div className={`job-card${isNew ? " new" : ""}`}>
      <div className="row between" style={{ alignItems: "flex-start", gap: 10 }}>
        {isNew ? (
          <div className="row" style={{ gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--green-d)", display: "inline-block" }} />
            <span className="label" style={{ color: "var(--green-d)" }}>New job · reply please</span>
          </div>
        ) : !job.scheduled_for ? (
          <div className="row pulse" style={{ gap: 4, color: "var(--red)" }}>
            <AlertCircle size={14} />
            <span className="label" style={{ color: "inherit" }}>🚨 URGENT Emergency Job</span>
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
      <div className="row between" style={{ alignItems: "flex-start", gap: 10 }}>
        <div className="stack" style={{ gap: 3, flex: 1 }}>
          <div className="display" style={{ fontSize: 17, fontWeight: 700 }}>
            {job.customer_name} · {titleCase(job.trade)}
          </div>
          <div className="small muted">
            {formatWhen(job.scheduled_for)}
            {job.address ? ` · ${job.address}` : ""}
          </div>
          {whyYou(job.explanation) && <span className="pill green" style={{ alignSelf: "flex-start" }}>Why you: {whyYou(job.explanation)}</span>}
        </div>
        {isSpeechSupported() && (
          <button
            type="button"
            className={`chip ${speaking ? "on" : ""}`}
            style={{
              padding: "4px 10px",
              gap: 6,
              background: speaking ? "var(--green-d)" : "var(--sand)",
              color: speaking ? "#fff" : "inherit",
              borderColor: speaking ? "transparent" : "var(--border)",
              cursor: "pointer",
            }}
            onClick={toggleSpeak}
            title="बोलकर सुनें (Listen to job details in Hindi)"
          >
            <Volume2 size={16} />
            <span style={{ fontSize: 12, fontWeight: 600 }}>{speaking ? "रुकें (Stop)" : "सुनें (Suno)"}</span>
          </button>
        )}
      </div>

      {message && <div className={`notice ${message.kind}`}>{message.text}</div>}

      <div className="divider" />

      {mode === "price" ? (
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
      ) : mode === "decline" ? (
        <div className="stack" style={{ gap: 16 }}>
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
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn danger grow" onClick={decline} disabled={busy || !reason}>
              {busy ? "Passing on…" : "Pass it on"}
            </button>
            <button type="button" className="btn outline" onClick={() => setMode("view")} disabled={busy}>
              Back
            </button>
          </div>
        </div>
      ) : isNew ? (
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
              📍 Open Google Maps Directions
            </a>
            {(!job.started_at && !job.end_photo_url) && (
              <button type="button" onClick={() => setMode("decline")} disabled={busy}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
                Can’t make it
              </button>
            )}
          </div>
          <div className="divider" />
          
          {proofMode && (
            <PhotoProofModal 
              mode={proofMode}
              onClose={() => setProofMode(null)}
              onSubmit={async (uri, lat, lng, ts) => {
                await run(async () => {
                  if (proofMode === "start") {
                    await api.kaam.verifyArrival(job.booking_id, uri, lat, lng, ts);
                  } else {
                    await api.kaam.verifyCompletion(job.booking_id, uri, lat, lng, ts);
                  }
                }, proofMode === "start" ? "Arrival verified!" : "Work marked as complete!");
              }}
            />
          )}

          {settlement ? (
            <SettlementCard settlement={settlement} role="worker" onChange={async () => { setSettlement(await api.settlement.get(job.booking_id)); await onChange(); }} />
          ) : brief && !settlementError ? (
            <div className="small muted">Loading the price on the table…</div>
          ) : !job.start_selfie_url ? (
            <div className="stack" style={{ gap: 6 }}>
              <button type="button" className="btn outline" style={{ minHeight: 50, borderColor: "var(--green-d)", color: "var(--green-d)" }} disabled={busy} onClick={() => setProofMode("start")}>
                <Camera size={18} />
                📸 Verify Arrival
              </button>
              <button type="button" className="btn green" style={{ minHeight: 50 }} disabled={true}>
                Start Work
              </button>
            </div>
          ) : !job.started_at ? (
            <div className="stack" style={{ gap: 6 }}>
              <div className="row" style={{ gap: 6, color: "var(--green-d)" }}>
                <Check size={18} />
                <span className="label" style={{ color: "inherit" }}>✓ Arrival Verified</span>
              </div>
              <button type="button" className="btn green" style={{ minHeight: 50 }} disabled={busy} onClick={() => run(() => api.kaam.startWork(job.booking_id, new Date().toISOString()))}>
                Start Work
              </button>
            </div>
          ) : !job.end_photo_url ? (
            <div className="stack" style={{ gap: 6 }}>
              <div className="row pulse" style={{ gap: 6, color: "var(--green-d)" }}>
                <span style={{ width: 12, height: 12, borderRadius: 999, background: "currentColor", display: "inline-block" }} />
                <span className="label" style={{ color: "inherit" }}>🟢 IN PROGRESS</span>
              </div>
              <button type="button" className="btn outline" style={{ minHeight: 50, borderColor: "var(--green-d)", color: "var(--green-d)" }} disabled={busy} onClick={() => setProofMode("end")}>
                <Camera size={18} />
                📸 Work Completion Verification
              </button>
            </div>
          ) : (
            <div className="stack" style={{ gap: 6 }}>
              <div className="row" style={{ gap: 6, color: "var(--green-d)" }}>
                <Check size={18} />
                <span className="label" style={{ color: "inherit" }}>✓ Work Completion Verified</span>
              </div>
              {settlementError && <div className="notice error">Could not load the settlement details. You can try proposing the price again.</div>}
              <div className="label">When finished</div>
              <button type="button" className="btn green" style={{ minHeight: 50 }} disabled={busy} onClick={() => setMode("price")}>
                <Check size={18} />
                Generate Bill / Propose Price
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
