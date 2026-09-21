import { useState, type FormEvent } from "react";
import { api, errorMessage, formatRupees, titleCase, type Dispute } from "../api";
import { Check, Cross } from "./Icons";

export interface DiscrepancyModalProps {
  bookingId: number;
  trade?: string;
  workerName?: string | null;
  chargedAmount?: number | null;
  standardAmount?: number | null;
  minFairAmount?: number | null;
  maxFairAmount?: number | null;
  onClose: () => void;
  onSuccess: (dispute: Dispute) => void;
}

export function DiscrepancyModal({
  bookingId,
  trade,
  workerName,
  chargedAmount,
  standardAmount,
  minFairAmount,
  maxFairAmount,
  onClose,
  onSuccess,
}: DiscrepancyModalProps) {
  const [expectedAmount, setExpectedAmount] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Dispute | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const parsedAmount = expectedAmount.trim() ? Number(expectedAmount) : null;
      if (parsedAmount !== null && (isNaN(parsedAmount) || parsedAmount < 0)) {
        throw new Error("Please enter a valid amount in rupees");
      }

      // 1. Submit to real backend dispute endpoint (POST /disputes)
      const dispute = await api.disputes.raise({
        booking_id: bookingId,
        kind: "payment",
        amount_rupees: parsedAmount,
        description: reason.trim() || null,
      });

      // 2. Also notify settlement engine if pending so status transitions to disputed
      try {
        await api.settlement.respond(bookingId, {
          action: "dispute",
          note: reason.trim() || null,
        });
      } catch {
        // Safe to ignore if already agreed or not waiting on customer
      }

      setResult(dispute);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: 16,
        boxSizing: "border-box",
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="discrepancy-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="sheet"
        style={{
          width: "100%",
          maxWidth: 420,
          maxHeight: "90vh",
          overflowY: "auto",
          background: "var(--white)",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.25)",
          borderRadius: "var(--radius-xl)",
          boxSizing: "border-box",
          padding: 20,
        }}
      >
        {result ? (
          /* Result UI: Display real backend response */
          <div className="stack" style={{ gap: 14 }}>
            <div className="row between" style={{ alignItems: "center" }}>
              <div className="row" style={{ gap: 8, alignItems: "center" }}>
                <span className="dot green" style={{ width: 28, height: 28 }}>
                  <Check size={18} />
                </span>
                <div
                  id="discrepancy-modal-title"
                  className="display"
                  style={{ fontSize: 18, fontWeight: 700, color: "var(--green-d)" }}
                >
                  ✓ Discrepancy Reported
                </div>
              </div>
              <button
                type="button"
                className="btn outline"
                style={{ padding: 4, minHeight: "auto" }}
                onClick={() => {
                  onClose();
                  onSuccess(result);
                }}
                aria-label="Close"
              >
                <Cross size={20} />
              </button>
            </div>

            <div className="row between" style={{ alignItems: "center" }}>
              <span
                className="badge"
                style={{
                  background: "var(--amber-t)",
                  color: "var(--amber-d)",
                  fontWeight: 700,
                  padding: "4px 10px",
                }}
              >
                Sent for Cooperative Review
              </span>
              <span className="tiny muted num">Dispute #{result.id}</span>
            </div>

            <div
              className="card soft stack"
              style={{
                gap: 8,
                background: "var(--paper-2)",
                border: "1px solid var(--line)",
                padding: "12px 14px",
              }}
            >
              <div className="row between small">
                <span className="muted">Booking:</span>
                <span className="num" style={{ fontWeight: 600 }}>
                  #{result.booking_id}
                </span>
              </div>
              {result.amount_rupees !== null && result.amount_rupees !== undefined && (
                <div className="row between small">
                  <span className="muted">Expected Amount:</span>
                  <span className="num" style={{ fontWeight: 700 }}>
                    {formatRupees(result.amount_rupees)}
                  </span>
                </div>
              )}
              {result.description && (
                <div className="stack" style={{ gap: 2 }}>
                  <span className="tiny muted">Reported Reason:</span>
                  <div className="small" style={{ fontStyle: "italic" }}>
                    “{result.description}”
                  </div>
                </div>
              )}
              <div className="row between small">
                <span className="muted">Status:</span>
                <span style={{ fontWeight: 600, color: "var(--indigo-d)" }}>
                  {result.status === "open" ? "Open (Cooperative Review)" : result.status}
                </span>
              </div>
              {result.resolution && (
                <div className="stack" style={{ gap: 2 }}>
                  <span className="tiny muted">Council Resolution:</span>
                  <div className="small">{result.resolution}</div>
                </div>
              )}
            </div>

            <div className="tiny muted" style={{ lineHeight: 1.4 }}>
              Your report has been submitted directly to the Sabha. The cooperative council
              hears both sides, verifies the work, and ensures billing aligns with the community rate card.
            </div>

            <button
              type="button"
              className="btn primary block"
              style={{ minHeight: 46 }}
              onClick={() => {
                onClose();
                onSuccess(result);
              }}
            >
              Done
            </button>
          </div>
        ) : (
          /* Dispute Form */
          <form className="stack" style={{ gap: 14 }} onSubmit={submit}>
            <div className="row between" style={{ alignItems: "center" }}>
              <div
                id="discrepancy-modal-title"
                className="display"
                style={{ fontSize: 18, fontWeight: 700 }}
              >
                ⚠️ Report Price Discrepancy
              </div>
              <button
                type="button"
                className="btn outline"
                style={{ padding: 4, minHeight: "auto" }}
                onClick={onClose}
                disabled={busy}
                aria-label="Close"
              >
                <Cross size={20} />
              </button>
            </div>

            <div className="tiny muted">
              Report overcharging or incorrect rates for Booking #{bookingId}. The cooperative council will review the job.
            </div>

            {/* Read-only Context Box */}
            <div
              className="card soft stack"
              style={{
                gap: 6,
                background: "var(--paper-2)",
                border: "1px solid var(--line)",
                padding: "10px 12px",
                borderRadius: 10,
              }}
            >
              {workerName && (
                <div className="row between small">
                  <span className="muted">Worker:</span>
                  <span style={{ fontWeight: 600 }}>{workerName}</span>
                </div>
              )}
              {trade && (
                <div className="row between small">
                  <span className="muted">Service:</span>
                  <span>{titleCase(trade)}</span>
                </div>
              )}
              {chargedAmount !== null && chargedAmount !== undefined && (
                <div className="row between small">
                  <span className="muted">Proposed / Charged:</span>
                  <span className="num" style={{ fontWeight: 700, color: "var(--ink)" }}>
                    {formatRupees(chargedAmount)}
                  </span>
                </div>
              )}
              {standardAmount !== null && standardAmount !== undefined && (
                <div className="row between small">
                  <span className="muted">Community Rate Card:</span>
                  <span className="num muted">
                    {formatRupees(standardAmount)}
                    {minFairAmount && maxFairAmount ? ` (${formatRupees(minFairAmount)}–${formatRupees(maxFairAmount)})` : ""}
                  </span>
                </div>
              )}
            </div>

            {/* Input 1: Expected / Reference Amount */}
            <div className="stack" style={{ gap: 4 }}>
              <label htmlFor="expected-amount-input" className="small" style={{ fontWeight: 600 }}>
                Expected / Fair Amount (₹)
              </label>
              <label className="field" style={{ minHeight: 46 }}>
                <span className="muted">₹</span>
                <input
                  id="expected-amount-input"
                  inputMode="decimal"
                  value={expectedAmount}
                  onChange={(e) => setExpectedAmount(e.target.value)}
                  placeholder={standardAmount ? String(standardAmount) : "e.g. 450"}
                  aria-label="Expected amount in rupees"
                  disabled={busy}
                  style={{ height: 42 }}
                />
              </label>
              <div className="tiny muted">The amount you expected to pay or believe is fair.</div>
            </div>

            {/* Input 2: Reason / Short Explanation */}
            <div className="stack" style={{ gap: 4 }}>
              <label htmlFor="discrepancy-reason-input" className="small" style={{ fontWeight: 600 }}>
                Reason / Short Explanation
              </label>
              <label className="field" style={{ minHeight: 70, alignItems: "flex-start", padding: "8px 12px" }}>
                <textarea
                  id="discrepancy-reason-input"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Worked fewer hours than charged, rate was above agreed standard..."
                  maxLength={1000}
                  rows={3}
                  disabled={busy}
                  style={{
                    width: "100%",
                    border: "none",
                    outline: "none",
                    background: "transparent",
                    resize: "vertical",
                    fontSize: 14,
                  }}
                  aria-label="Reason for discrepancy"
                />
              </label>
              <div className="tiny muted">Shared with the cooperative council (Sabha) for review.</div>
            </div>

            {error && (
              <div className="notice error" style={{ wordBreak: "break-word" }}>
                {error}
              </div>
            )}

            <div className="row" style={{ gap: 8, marginTop: 4 }}>
              <button
                type="button"
                className="btn outline"
                style={{ minHeight: 46, minWidth: 80 }}
                onClick={onClose}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn primary grow"
                style={{ minHeight: 46 }}
                disabled={busy || (!expectedAmount.trim() && !reason.trim())}
              >
                {busy ? "Submitting…" : "Submit Discrepancy"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
