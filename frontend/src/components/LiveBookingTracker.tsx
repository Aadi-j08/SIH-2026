import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  api,
  errorMessage,
  formatRupees,
  formatWhen,
  titleCase,
  type BookingDetail,
  type Settlement,
} from "../api";
import {
  Check,
  Star,
  TRADE_ICONS,
} from "./Icons";
import { SettlementCard } from "./Settlement";

interface LiveBookingTrackerProps {
  detail: BookingDetail;
  settlement: Settlement | null;
  onRefresh: () => void;
}

export function LiveBookingTracker({
  detail,
  settlement,
  onRefresh,
}: LiveBookingTrackerProps) {
  const { booking, assignment, payment_ledger, rating } = detail;
  const status = booking.status;
  const IconFor = TRADE_ICONS[booking.trade] ?? TRADE_ICONS.plumbing;

  // Calculate simulated ETA & distance based on assignment status
  const [etaMins, setEtaMins] = useState(12);
  const [distanceKm] = useState(0.8);

  useEffect(() => {
    if (status === "assigned") {
      const interval = setInterval(() => {
        setEtaMins((prev) => (prev > 2 ? prev - 1 : 2));
      }, 45000);
      return () => clearInterval(interval);
    }
  }, [status]);

  // Determine active step (0 = Placed, 1 = Assigned, 2 = On the Way, 3 = Completed)
  let activeStepIndex = 0;
  if (status === "pending") activeStepIndex = 0;
  else if (status === "assigned" && !settlement) activeStepIndex = 2; // On the way / arriving
  else if (settlement && settlement.status !== "agreed") activeStepIndex = 2; // In progress
  else if (status === "completed" || settlement?.status === "agreed") activeStepIndex = 3;

  const STEPS = [
    { title: "Requested", hi: "अनुरोध दर्ज", desc: "Order received" },
    { title: "Artisan Matched", hi: "कारीगर चुना गया", desc: "Fair Bipartite Match" },
    { title: "En Route & Service", hi: "रास्ते में / काम चालू", desc: "Arriving at location" },
    { title: "Completed & Paid", hi: "कार्य संपन्न", desc: "Direct 85% settlement" },
  ];

  return (
    <div className="zomato-tracker stack" style={{ gap: 20 }}>
      {/* 1. Header Banner with Live Pulse */}
      <div
        className="card tracker-header"
        style={{
          background: "linear-gradient(135deg, #0F172A 0%, #1E293B 100%)",
          color: "#F8FAFC",
          borderRadius: 20,
          padding: "24px 20px",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          boxShadow: "0 12px 30px -10px rgba(0, 0, 0, 0.5)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: -40,
            right: -40,
            width: 140,
            height: 140,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        <div className="row between" style={{ alignItems: "flex-start", marginBottom: 16 }}>
          <div className="stack" style={{ gap: 4 }}>
            <div className="row" style={{ gap: 8, alignItems: "center" }}>
              <span
                style={{
                  display: "inline-block",
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: status === "completed" ? "#10B981" : "#F59E0B",
                  boxShadow: status === "completed" ? "0 0 12px #10B981" : "0 0 12px #F59E0B",
                  animation: status === "completed" ? "none" : "pulse 2s infinite",
                }}
              />
              <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.08em", color: "#94A3B8", textTransform: "uppercase" }}>
                Live Service Radar · लाइव ट्रैकिंग
              </span>
            </div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#FFFFFF" }}>
              {status === "pending" && "Finding Nearest Cooperative Artisan..."}
              {status === "assigned" && `Artisan Arriving in ~${etaMins} Mins`}
              {status === "completed" && "Service Successfully Completed!"}
            </h2>
            <div className="row" style={{ gap: 6, alignItems: "center", fontSize: 14, color: "#CBD5E1" }}>
              <IconFor size={16} />
              <span>Booking #{booking.id} · {titleCase(booking.trade)} · {formatWhen(booking.scheduled_for)}</span>
            </div>
          </div>

          <span
            style={{
              padding: "6px 14px",
              borderRadius: 20,
              fontSize: 12,
              fontWeight: 700,
              background: status === "completed" ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)",
              color: status === "completed" ? "#34D399" : "#FBBF24",
              border: `1px solid ${status === "completed" ? "rgba(16, 185, 129, 0.4)" : "rgba(245, 158, 11, 0.4)"}`,
            }}
          >
            {status === "pending" ? "Matching" : status === "assigned" ? "En Route" : "Completed"}
          </span>
        </div>

        {/* 2. Swiggy/Zomato Style 4-Step Animated Progress Line */}
        <div className="tracker-timeline" style={{ marginTop: 24, marginBottom: 8 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", position: "relative", gap: 8 }}>
            {STEPS.map((step, idx) => {
              const isDone = idx < activeStepIndex;
              const isCurrent = idx === activeStepIndex;
              return (
                <div key={step.title} style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", position: "relative" }}>
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 13,
                      fontWeight: 800,
                      marginBottom: 8,
                      zIndex: 2,
                      background: isDone ? "#10B981" : isCurrent ? "#F59E0B" : "#334155",
                      color: "#FFFFFF",
                      boxShadow: isCurrent ? "0 0 16px rgba(245, 158, 11, 0.8)" : isDone ? "0 0 10px rgba(16, 185, 129, 0.5)" : "none",
                      border: "2px solid #0F172A",
                      transition: "all 0.4s ease",
                    }}
                  >
                    {isDone ? <Check size={16} /> : idx + 1}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: isCurrent ? 800 : 600, color: isCurrent ? "#F59E0B" : isDone ? "#34D399" : "#64748B" }}>
                    {step.title}
                  </div>
                  <div style={{ fontSize: 10, color: "#94A3B8" }}>{step.hi}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 3. Live Vector Map Preview (Zomato delivery radar style) */}
      {status === "assigned" && (
        <div
          className="card map-preview-radar"
          style={{
            background: "#1E293B",
            borderRadius: 20,
            overflow: "hidden",
            padding: 0,
            border: "1px solid rgba(255, 255, 255, 0.1)",
            position: "relative",
            minHeight: 200,
          }}
        >
          {/* Stylized SVG Map Graphics */}
          <svg width="100%" height="200" viewBox="0 0 600 200" style={{ display: "block", background: "#0F172A" }}>
            <defs>
              <linearGradient id="routeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#10B981" />
                <stop offset="100%" stopColor="#06B6D4" />
              </linearGradient>
              <pattern id="mapGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1" />
              </pattern>
            </defs>

            {/* Map Roads Grid */}
            <rect width="100%" height="100%" fill="url(#mapGrid)" />
            <path d="M -50 80 Q 200 40, 350 120 T 650 100" stroke="#334155" strokeWidth="18" fill="none" strokeLinecap="round" />
            <path d="M 120 0 L 120 220" stroke="#334155" strokeWidth="12" fill="none" />
            <path d="M 460 0 L 460 220" stroke="#334155" strokeWidth="12" fill="none" />

            {/* Active GPS Route */}
            <path
              d="M 140 100 Q 280 60, 460 110"
              stroke="url(#routeGradient)"
              strokeWidth="5"
              strokeDasharray="8 6"
              fill="none"
            >
              <animate attributeName="stroke-dashoffset" from="100" to="0" dur="3s" repeatCount="indefinite" />
            </path>

            {/* Worker Pin & Marker */}
            <g transform="translate(140, 100)">
              <circle r="22" fill="rgba(16, 185, 129, 0.2)">
                <animate attributeName="r" values="18;28;18" dur="2s" repeatCount="indefinite" />
              </circle>
              <circle r="16" fill="#10B981" />
              <text x="0" y="5" fill="#FFFFFF" fontSize="11" textAnchor="middle" fontWeight="bold">🔧</text>
              <text x="0" y="32" fill="#34D399" fontSize="11" textAnchor="middle" fontWeight="bold">Artisan ({distanceKm} km)</text>
            </g>

            {/* Customer Home Pin */}
            <g transform="translate(460, 110)">
              <circle r="20" fill="rgba(6, 182, 212, 0.25)">
                <animate attributeName="r" values="16;26;16" dur="2s" repeatCount="indefinite" />
              </circle>
              <circle r="14" fill="#06B6D4" />
              <text x="0" y="4" fill="#FFFFFF" fontSize="10" textAnchor="middle" fontWeight="bold">🏡</text>
              <text x="0" y="30" fill="#E2E8F0" fontSize="11" textAnchor="middle" fontWeight="bold">Your Address</text>
            </g>
          </svg>

          {/* Floating Radar Tag */}
          <div
            style={{
              position: "absolute",
              top: 12,
              left: 14,
              padding: "5px 12px",
              background: "rgba(15, 23, 42, 0.85)",
              backdropFilter: "blur(8px)",
              borderRadius: 12,
              color: "#F8FAFC",
              fontSize: 12,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 6,
              border: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10B981" }} />
            Live Dispatch · GPS Accurate
          </div>
        </div>
      )}

      {/* 4. Swiggy-Style Artisan Profile Card with Quick Actions */}
      {assignment && (
        <div
          className="card artisan-profile-card"
          style={{
            background: "#FFFFFF",
            borderRadius: 20,
            padding: 22,
            boxShadow: "0 8px 24px -6px rgba(0, 0, 0, 0.08)",
            border: "1px solid #E2E8F0",
          }}
        >
          <div className="row between" style={{ alignItems: "center", marginBottom: 16 }}>
            <div className="row" style={{ gap: 14, alignItems: "center" }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, #6366F1 0%, #4F46E5 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 24,
                  color: "#FFFFFF",
                  fontWeight: 800,
                  boxShadow: "0 4px 12px rgba(99, 102, 241, 0.3)",
                }}
              >
                {assignment.worker.name.charAt(0)}
              </div>
              <div className="stack" style={{ gap: 2 }}>
                <div className="row" style={{ gap: 8, alignItems: "center" }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: "#0F172A" }}>{assignment.worker.name}</div>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 10,
                      fontSize: 11,
                      fontWeight: 700,
                      background: "#ECFDF5",
                      color: "#059669",
                    }}
                  >
                    🛡️ Verified Member
                  </span>
                </div>
                <div style={{ fontSize: 13, color: "#64748B" }}>
                  {titleCase(assignment.worker.trade)} · {assignment.worker.rating ? `⭐ ${Number(assignment.worker.rating).toFixed(1)} / 5.0` : "⭐ 5.0 (New Member)"}
                </div>
              </div>
            </div>

            {/* Quick Action: Call Worker */}
            {assignment.worker.phone ? (
              <a
                href={`tel:${assignment.worker.phone}`}
                className="btn primary"
                style={{
                  background: "#10B981",
                  color: "#FFFFFF",
                  padding: "10px 18px",
                  borderRadius: 14,
                  fontSize: 14,
                  fontWeight: 700,
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.3)",
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" />
                </svg>
                Call Artisan
              </a>
            ) : null}
          </div>

          {/* Transparent Fair Allocation Reason Tag */}
          {assignment.explanation ? (
            <div
              style={{
                background: "#F8FAFC",
                padding: "12px 14px",
                borderRadius: 12,
                border: "1px solid #E2E8F0",
                fontSize: 13,
                color: "#334155",
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
              }}
            >
              <span style={{ fontSize: 16 }}>⚖️</span>
              <div>
                <strong>Why this artisan was assigned:</strong> {assignment.explanation}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* 5. Settlement / Bill Card */}
      {settlement && (
        <section className="stack">
          <div className="label" style={{ fontWeight: 700 }}>{settlement.status === "agreed" ? "Your Payment Receipt" : "Bill on the Table"}</div>
          <SettlementCard settlement={settlement} role="customer" onChange={onRefresh} />
        </section>
      )}

      {/* 6. Transparent 85 / 10 / 5 Payment Ledger (when completed) */}
      {status === "completed" && payment_ledger && payment_ledger.length > 0 && (
        <section className="stack">
          <div className="label" style={{ fontWeight: 700 }}>Transparent Cooperative Payment Receipt</div>
          <div className="card stack" style={{ gap: 10, background: "#FFFFFF", borderRadius: 20, padding: 20, border: "1px solid #E2E8F0" }}>
            <div className="row between">
              <div style={{ fontWeight: 800, fontSize: 16 }}>Total Bill Paid</div>
              <div className="display num" style={{ fontSize: 22, fontWeight: 800, color: "#0F172A" }}>
                {formatRupees(payment_ledger.reduce((sum, e) => sum + e.amount_rupees, 0))}
              </div>
            </div>
            <div className="split" style={{ height: 10, borderRadius: 6, overflow: "hidden", display: "flex" }}>
              {payment_ledger.map((e, i) => (
                <div key={e.party} style={{ width: `${e.share_percent}%`, background: ["#10B981", "#6366F1", "#F59E0B"][i] }} />
              ))}
            </div>
            {payment_ledger.map((e, i) => (
              <div className="row small" key={e.party} style={{ alignItems: "center" }}>
                <span className="swatch" style={{ width: 10, height: 10, borderRadius: "50%", background: ["#10B981", "#6366F1", "#F59E0B"][i], display: "inline-block", marginRight: 8 }} />
                <span className="grow" style={{ color: "#334155", fontWeight: 600 }}>{{ worker: "Direct Artisan Take-Home", welfare_fund: "Cooperative Welfare & Health Fund", platform_operations: "Platform Operations & Hosting" }[e.party]}</span>
                <span className="num" style={{ fontWeight: 800, color: "#0F172A" }}>{formatRupees(e.amount_rupees)}</span>
                <span className="num muted" style={{ width: 42, textAlign: "right", color: "#64748B" }}>({e.share_percent}%)</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 7. Rating Form (if completed and unrated) */}
      {status === "completed" && !rating && (
        <InlineRatingForm bookingId={booking.id} onRated={onRefresh} />
      )}

      {/* 8. Rated Confirmation Badge */}
      {status === "completed" && rating && (
        <div
          className="card"
          style={{
            background: "#ECFDF5",
            border: "1px solid #A7F3D0",
            borderRadius: 16,
            padding: 18,
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div style={{ width: 36, height: 36, borderRadius: "50%", background: "#10B981", color: "#FFF", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Check size={20} />
          </div>
          <div>
            <div style={{ fontWeight: 800, color: "#065F46" }}>You rated this job {rating.rating} / 5 Stars</div>
            {rating.comment && <div style={{ fontSize: 13, color: "#047857" }}>“{rating.comment}”</div>}
          </div>
        </div>
      )}

      <div className="row between" style={{ marginTop: 8 }}>
        <Link to="/ghar/home" className="btn outline" style={{ borderRadius: 14 }}>
          ← Book Another Service
        </Link>
        <button type="button" onClick={onRefresh} className="btn outline" style={{ borderRadius: 14 }}>
          🔄 Refresh Live Status
        </button>
      </div>
    </div>
  );
}

function InlineRatingForm({ bookingId, onRated }: { bookingId: number; onRated: () => void }) {
  const [stars, setStars] = useState(5);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.bookings.rate(bookingId, stars, comment.trim() || undefined);
      onRated();
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <section className="stack">
      <div className="label" style={{ fontWeight: 700 }}>Rate Your Cooperative Experience</div>
      <div className="card stack" style={{ background: "#FFFFFF", borderRadius: 20, padding: 20, border: "1px solid #E2E8F0" }}>
        <div className="row" style={{ gap: 6 }} role="radiogroup" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              type="button"
              key={n}
              onClick={() => setStars(n)}
              role="radio"
              aria-checked={stars === n}
              style={{ background: "none", border: 0, padding: 4, cursor: "pointer", color: n <= stars ? "#F59E0B" : "#CBD5E1" }}
            >
              <Star size={32} filled={n <= stars} />
            </button>
          ))}
        </div>
        <div className="field" style={{ marginTop: 10 }}>
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Share feedback for the artisan and community..."
            maxLength={500}
            style={{ borderRadius: 12 }}
          />
        </div>
        {error && <div className="notice error">{error}</div>}
        <button type="button" className="btn primary" disabled={busy} onClick={submit} style={{ background: "#10B981", color: "#FFF", borderRadius: 12, marginTop: 8 }}>
          {busy ? "Submitting..." : "Submit Review & Rating"}
        </button>
      </div>
    </section>
  );
}
