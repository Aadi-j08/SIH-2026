import { useEffect, useState } from "react";
import { type Booking, titleCase } from "../api";
import { Pin, TRADE_ICONS } from "./Icons";

interface AsapFindingWorkerProps {
  booking: Booking;
  onCancel: () => Promise<void>;
}

const CYCLING_STATUSES = [
  "Searching available workers...",
  "Searching nearby workers",
  "Checking worker availability",
  "Matching the best available worker",
  "Confirming worker assignment",
];

export function AsapFindingWorker({ booking, onCancel }: AsapFindingWorkerProps) {
  const [statusIndex, setStatusIndex] = useState(0);
  const [showConfirm, setShowConfirm] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setStatusIndex((prev) => (prev + 1) % CYCLING_STATUSES.length);
    }, 2600);
    return () => clearInterval(interval);
  }, []);

  const IconFor = TRADE_ICONS[booking.trade] ?? TRADE_ICONS.plumbing;

  const handleConfirmCancel = async () => {
    setCancelling(true);
    setCancelError(null);
    try {
      await onCancel();
    } catch (err: unknown) {
      setCancelError(err instanceof Error ? err.message : "Failed to cancel booking");
      setCancelling(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 24, padding: "8px 0" }}>
      {/* Styles for radar pulse and cycling animation */}
      <style>{`
        @keyframes asap-pulse-ring {
          0% {
            transform: scale(0.65);
            opacity: 0.9;
          }
          50% {
            opacity: 0.5;
          }
          100% {
            transform: scale(1.6);
            opacity: 0;
          }
        }
        @keyframes asap-radar-sweep {
          0% {
            transform: rotate(0deg);
          }
          100% {
            transform: rotate(360deg);
          }
        }
        @keyframes asap-glow {
          0%, 100% {
            transform: scale(1);
            box-shadow: 0 0 20px rgba(var(--accent-rgb, 198, 93, 38), 0.4);
          }
          50% {
            transform: scale(1.05);
            box-shadow: 0 0 32px rgba(var(--accent-rgb, 198, 93, 38), 0.7);
          }
        }
        .asap-radar-box {
          position: relative;
          width: 200px;
          height: 200px;
          margin: 12px auto;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .asap-pulse-circle {
          position: absolute;
          border-radius: 50%;
          border: 2px solid var(--accent);
          pointer-events: none;
        }
        .asap-pulse-1 {
          width: 90px;
          height: 90px;
          animation: asap-pulse-ring 3s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite;
        }
        .asap-pulse-2 {
          width: 130px;
          height: 130px;
          animation: asap-pulse-ring 3s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite 1s;
        }
        .asap-pulse-3 {
          width: 170px;
          height: 170px;
          animation: asap-pulse-ring 3s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite 2s;
        }
        .asap-sweep-disc {
          position: absolute;
          width: 180px;
          height: 180px;
          border-radius: 50%;
          background: conic-gradient(from 0deg, transparent 0deg 280deg, rgba(var(--accent-rgb, 198, 93, 38), 0.25) 360deg);
          animation: asap-radar-sweep 4s linear infinite;
          pointer-events: none;
        }
        .asap-center-badge {
          position: relative;
          width: 68px;
          height: 68px;
          border-radius: 50%;
          background: var(--accent);
          color: #ffffff;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 2;
          animation: asap-glow 2.5s ease-in-out infinite;
        }
        .asap-cycling-text {
          font-size: 17px;
          font-weight: 700;
          color: var(--ink);
          transition: opacity 0.3s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
        }
        .asap-dot-flashing {
          display: inline-block;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--accent);
          animation: asap-dot 1.2s infinite ease-in-out;
        }
        @keyframes asap-dot {
          0%, 100% { opacity: 0.2; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>

      {/* Header */}
      <div className="stack" style={{ gap: 6, textAlign: "center" }}>
        <h1 style={{ fontSize: 24, margin: 0 }}>🔍 Finding a nearby worker</h1>
        <div className="sub" style={{ justifyContent: "center" }}>
          Looking for an available worker near you...
        </div>
      </div>

      {/* Radar Animation Area */}
      <div className="card" style={{ padding: "28px 16px", textAlign: "center", background: "var(--paper-2)", border: "1.5px solid var(--line)" }}>
        <div className="asap-radar-box">
          <div className="asap-pulse-circle asap-pulse-1" />
          <div className="asap-pulse-circle asap-pulse-2" />
          <div className="asap-pulse-circle asap-pulse-3" />
          <div className="asap-sweep-disc" />
          <div className="asap-center-badge">
            <IconFor size={32} />
          </div>
        </div>

        {/* Cycling Status Text */}
        <div className="stack" style={{ gap: 6, marginTop: 12 }}>
          <div className="asap-cycling-text">
            <span>{CYCLING_STATUSES[statusIndex]}</span>
            <span className="asap-dot-flashing" />
          </div>
          <div className="tiny muted">
            Cooperative fair allocation · matching on proximity &amp; workload
          </div>
        </div>
      </div>

      {/* Booking Summary Card */}
      <div className="card stack" style={{ gap: 12 }}>
        <div className="row between" style={{ alignItems: "center" }}>
          <div className="row" style={{ gap: 8, alignItems: "center" }}>
            <span className="badge" style={{ background: "var(--accent-t)", color: "var(--accent-d)", fontWeight: 800 }}>
              🚨 Emergency / Urgent
            </span>
            <span style={{ fontWeight: 700, fontSize: 16 }}>{titleCase(booking.trade)}</span>
          </div>
          <span className="small muted">Booking #{booking.id}</span>
        </div>

        <div className="row small" style={{ gap: 8, alignItems: "flex-start", color: "var(--ink-2)" }}>
          <Pin size={18} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 1 }} />
          <span>{booking.address || "Current Location"}</span>
        </div>
      </div>

      {/* Cancel Button */}
      <button
        type="button"
        className="btn outline"
        onClick={() => setShowConfirm(true)}
        style={{
          color: "#b91c1c",
          borderColor: "#fca5a5",
          background: "#fff",
          minHeight: 46,
          fontWeight: 600,
        }}
      >
        Cancel Booking
      </button>

      {/* Confirmation Modal */}
      {showConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="cancel-modal-title"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.65)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
            zIndex: 9999,
          }}
        >
          <div
            className="card stack"
            style={{
              width: "100%",
              maxWidth: 400,
              gap: 16,
              background: "var(--white)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.25)",
            }}
          >
            <div className="stack" style={{ gap: 6 }}>
              <h2 id="cancel-modal-title" style={{ fontSize: 18, margin: 0, color: "var(--ink)" }}>
                Cancel this booking?
              </h2>
              <p className="small muted" style={{ margin: 0, lineHeight: 1.5 }}>
                Are you sure you want to cancel your request for <strong>{titleCase(booking.trade)}</strong>? If you wait, an available worker will be assigned shortly.
              </p>
            </div>

            {cancelError && <div className="notice error">{cancelError}</div>}

            <div className="row" style={{ gap: 10, justifyContent: "flex-end", marginTop: 8 }}>
              <button
                type="button"
                className="btn outline"
                disabled={cancelling}
                onClick={() => setShowConfirm(false)}
                style={{ flex: 1 }}
              >
                Keep Searching
              </button>
              <button
                type="button"
                className="btn primary"
                disabled={cancelling}
                onClick={handleConfirmCancel}
                style={{
                  flex: 1,
                  background: "#dc2626",
                  borderColor: "#dc2626",
                  color: "#fff",
                }}
              >
                {cancelling ? "Cancelling…" : "Yes, Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
