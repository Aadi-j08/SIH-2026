import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  DEFAULT_LOCATION,
  TRADES,
  api,
  errorMessage,
  titleCase,
  storageGet,
  storageSet,
  type BookingDetail,
  type Settlement,
} from "../api";
import { useAuth } from "../lib/auth";
import { useLive } from "../lib/live";
import { ArrowRight, Check, Clock, Locate, Pin, Star, TRADE_ICONS } from "../components/Icons";
import { RateHint, SettlementCard } from "../components/Settlement";
import { AsapFindingWorker } from "../components/AsapFindingWorker";
import AssistantPanel from "../components/AssistantPanel";
import { AIVoiceSearchBar } from "../components/AIVoiceSearchBar";
import { LiveBookingTracker } from "../components/LiveBookingTracker";

function computeDistanceKm(lat1?: number | null, lon1?: number | null, lat2?: number | null, lon2?: number | null): number | null {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return null;
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const km = Math.round(R * c * 10) / 10;
  return isNaN(km) ? null : km;
}

const LAST_BOOKING_KEY = "sahakarsetu.lastBooking";

export default function Customer() {
  const { bookingId } = useParams();
  return bookingId ? <BookingStatus bookingId={Number(bookingId)} /> : <BookingForm />;
}

// ── booking form ─────────────────────────────────────────────────────

type When = "asap" | "tomorrow" | "custom";

function tomorrowAt(hour: number): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(hour, 0, 0, 0);
  return toLocalIso(date);
}

function toLocalIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function BookingForm() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [trade, setTrade] = useState<string>("plumbing");
  const [address, setAddress] = useState("");
  const [location, setLocation] = useState({ ...DEFAULT_LOCATION, fromGps: false });
  const [locating, setLocating] = useState(false);
  const [when, setWhen] = useState<When>("tomorrow");
  const [custom, setCustom] = useState(tomorrowAt(10));
  const [name, setName] = useState(user?.name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const lastBooking = Number(storageGet(LAST_BOOKING_KEY) ?? 0) || null;

  const useGps = () => {
    if (!navigator.geolocation) {
      setError("This browser can't share your location; using the cooperative's area instead.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, label: "your location", fromGps: true });
        setLocating(false);
      },
      () => {
        setError("Couldn't get a GPS fix; using the cooperative's area instead.");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 8000 },
    );
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const booking = await api.bookings.create({
        customer_name: name.trim(),
        customer_phone: phone.trim() || null,
        trade,
        latitude: location.latitude,
        longitude: location.longitude,
        address: address.trim() || null,
        scheduled_for: when === "asap" ? null : when === "tomorrow" ? tomorrowAt(10) : custom,
      });
      storageSet(LAST_BOOKING_KEY, String(booking.id));
      navigate(`/ghar/home/${booking.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="stack" style={{ gap: 6 }}>
        <h1>Book a service</h1>
        <div className="sub">
          {user ? (
            <>
              Namaste, {user.name.split(" ")[0]}
              {user.locality ? ` · ${user.locality}` : ""}
            </>
          ) : (
            "A fairly-chosen worker from your local cooperative."
          )}
        </div>
      </div>

      <AIVoiceSearchBar
        onSelectTrade={(t) => {
          const map: Record<string, string> = {
            plumber: "plumbing",
            electrician: "electrical",
            carpenter: "carpentry",
            painter: "painting",
            mason: "cleaning", // or closest trade
          };
          setTrade(map[t] || t);
        }}
      />

      <AssistantPanel role="customer" latitude={location.latitude} longitude={location.longitude} onBooking={(id) => navigate(`/ghar/home/${id}`)} />

      <form className="stack" onSubmit={submit}>

      <section className="stack">
        <div className="label">What do you need?</div>
        <div className="grid-3" role="radiogroup" aria-label="Service">
          {TRADES.map((t) => {
            const IconFor = TRADE_ICONS[t];
            return (
              <button type="button" key={t} className={`tile${trade === t ? " on" : ""}`} onClick={() => setTrade(t)} role="radio" aria-checked={trade === t}>
                <IconFor />
                {titleCase(t)}
              </button>
            );
          })}
        </div>
        <RateHint trade={trade} />
      </section>

      <section className="stack">
        <div className="label">Where?</div>
        <label className="field">
          <Pin size={20} style={{ color: "var(--accent)" }} />
          <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="House no., area, city" autoComplete="street-address" />
          <button type="button" className="adorn" onClick={useGps} disabled={locating}>
            <Locate size={16} />
            {locating ? "…" : "GPS"}
          </button>
        </label>
        <div className="tiny muted">
          Matching workers near {location.fromGps ? "your GPS location" : `${location.label} (tap GPS for your exact spot)`}.
        </div>
      </section>

      <section className="stack">
        <div className="label">When?</div>
        <div className="chips" role="radiogroup" aria-label="When">
          <button type="button" className={`chip${when === "asap" ? " on" : ""}`} onClick={() => setWhen("asap")}>
            As soon as possible
          </button>
          <button type="button" className={`chip${when === "tomorrow" ? " on" : ""}`} onClick={() => setWhen("tomorrow")}>
            <Clock size={16} />
            Tomorrow, 10:00
          </button>
          <button type="button" className={`chip${when === "custom" ? " on" : ""}`} onClick={() => setWhen("custom")}>
            Pick a time
          </button>
        </div>
        {when === "custom" && (
          <label className="field">
            <input type="datetime-local" value={custom} min={toLocalIso(new Date())} onChange={(e) => setCustom(e.target.value)} required />
          </label>
        )}
      </section>

      <section className="stack">
        <div className="label">Your details</div>
        <div className="tiny muted">From your Ghar account — change them here if this booking is for someone else.</div>
        <label className="field">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" required minLength={1} />
        </label>
        <label className="field">
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Mobile number" inputMode="tel" autoComplete="tel" maxLength={20} />
        </label>
      </section>

      {error && <div className="notice error">{error}</div>}
      {lastBooking && (
        <Link to={`/ghar/home/${lastBooking}`} className="small">
          See your last booking (#{lastBooking}) →
        </Link>
      )}

      <div className="sticky-cta">
        <button type="submit" className="btn primary block" disabled={submitting || !name.trim()}>
          {submitting ? "Sending…" : "Find a worker"}
          {!submitting && <ArrowRight size={20} />}
        </button>
        <div className="tiny muted" style={{ textAlign: "center" }}>
          No advance payment and nothing is charged here. You agree the price with the worker when the job ends and pay them directly — 10% of it is their contribution to the workers' welfare fund.
        </div>
      </div>
    </form>
    </div>
  );
}

// ── booking status ───────────────────────────────────────────────────

function BookingStatus({ bookingId }: { bookingId: number }) {
  const [detail, setDetail] = useState<BookingDetail | null>(null);
  const [settlement, setSettlement] = useState<Settlement | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const next = await api.bookings.detail(bookingId);
      setDetail(next);
      if (next.assignment) setSettlement(await api.settlement.get(bookingId));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  // live: reload the moment this booking changes; slow poll as a safety net
  const { live } = useLive(() => void load(), { filter: (e) => e.booking_id === bookingId || e.topic === "allocation" });
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), live ? 30000 : 4000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId, live]);

  if (error && !detail) {
    return (
      <div className="page">
        <div className="notice error">{error}</div>
        <Link to="/ghar/home" className="btn outline">
          Back to booking
        </Link>
      </div>
    );
  }
  if (!detail) return <div className="page muted">Loading…</div>;

  const { booking, assignment, payment_ledger, rating } = detail;
  const status = booking.status;
  const isAsap = booking.scheduled_for === null;
  const IconFor = TRADE_ICONS[booking.trade] ?? TRADE_ICONS.plumbing;

  if (isAsap && status === "pending") {
    return (
      <div className="page">
        <AsapFindingWorker
          booking={booking}
          onCancel={async () => {
            await api.bookings.cancel(booking.id);
            await load();
          }}
        />
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="page">
        <section className="stack" style={{ gap: 16, textAlign: "center", padding: "40px 16px" }}>
          <div className="badge" style={{ background: "#fee2e2", color: "#991b1b", padding: "6px 14px", alignSelf: "center", fontSize: 13, fontWeight: 700 }}>
            Cancelled
          </div>
          <h2 style={{ margin: 0 }}>Booking #{booking.id} Cancelled</h2>
          <p className="small muted" style={{ margin: 0, maxWidth: 380, alignSelf: "center", lineHeight: 1.5 }}>
            Your request for {titleCase(booking.trade)} was cancelled. You can place a new booking whenever you are ready.
          </p>
          <Link to="/ghar/home" className="btn primary" style={{ alignSelf: "center", minHeight: 44, padding: "0 24px", marginTop: 8 }}>
            Book another service
          </Link>
        </section>
      </div>
    );
  }

  let asapBanner = {
    badge: "✓ Worker Found",
    badgeBg: "var(--green-t)",
    badgeColor: "var(--green-d)",
    headline: "✓ Worker Found",
    sub: assignment ? `Assigned to ${assignment.worker.name} · Confirming assignment` : "Cooperative assigned a worker",
  };

  if (assignment?.started_at) {
    asapBanner = {
      badge: "🟢 In Progress",
      badgeBg: "var(--green-t)",
      badgeColor: "var(--green-d)",
      headline: "Work in Progress",
      sub: `${assignment.worker.name.split(" ")[0]} is currently working on your request`,
    };
  } else if (assignment?.start_selfie_url) {
    asapBanner = {
      badge: "📍 Arrived",
      badgeBg: "var(--accent-t)",
      badgeColor: "var(--accent-d)",
      headline: "Worker Has Arrived",
      sub: `${assignment.worker.name.split(" ")[0]} has arrived at your address`,
    };
  } else if (assignment?.accepted_at) {
    asapBanner = {
      badge: "🚗 On The Way",
      badgeBg: "var(--indigo-t)",
      badgeColor: "var(--indigo-d)",
      headline: "Worker is On The Way",
      sub: `${assignment.worker.name.split(" ")[0]} accepted and is en route to you`,
    };
  }

  const workerDist = assignment
    ? computeDistanceKm(booking.latitude, booking.longitude, assignment.worker.latitude, assignment.worker.longitude)
    : null;
  const workerDistanceText = workerDist !== null ? ` · ${workerDist} km away` : "";
  const workerMeta = assignment
    ? `${titleCase(assignment.worker.trade)} · ${assignment.worker.rating ? `rated ${Number(assignment.worker.rating).toFixed(1)}` : "new member"}${workerDistanceText}`
    : "";

  return (
    <div className="page" style={{ maxWidth: 640, margin: "0 auto", paddingBottom: 60 }}>
      <LiveBookingTracker detail={detail} settlement={settlement} onRefresh={load} />
      <div className="stack" style={{ gap: 6 }}>
        <div className="row between">
          <h1>Booking #{booking.id}</h1>
          <StatusPill status={status} />
        </div>
        <div className="row sub">
          <IconFor size={18} />
          {titleCase(booking.trade)} · {formatWhen(booking.scheduled_for)}
          {booking.address ? ` · ${booking.address}` : ""}
        </div>
      </div>

      {status === "pending" && (
        <section className="stack">
          <div className="card soft stack" style={{ gap: 4 }}>
            <div style={{ fontWeight: 700 }}>The cooperative is choosing your worker</div>
            <div className="small muted">Workers are ranked on distance, who has had the fewest jobs this week, rating and availability — not just who's nearest.</div>
          </div>
          <div className="tiny muted">You will see who is coming, and why they were chosen, as soon as the cooperative assigns the job.</div>
        </section>
      )}

      {assignment && (
        <section className="stack">
          {isAsap && (
            <div className="card" style={{ background: "var(--paper-2)", border: "1.5px solid var(--line)", padding: "14px 16px" }}>
              <div className="row between" style={{ alignItems: "center" }}>
                <span className="badge" style={{ background: asapBanner.badgeBg, color: asapBanner.badgeColor, fontWeight: 700, padding: "4px 10px" }}>
                  {asapBanner.badge}
                </span>
                <span className="badge" style={{ background: "var(--accent-t)", color: "var(--accent-d)", fontWeight: 800 }}>
                  ⚡ ASAP
                </span>
              </div>
              <div style={{ fontWeight: 700, fontSize: 17, marginTop: 8 }}>{asapBanner.headline}</div>
              <div className="small muted" style={{ marginTop: 2 }}>{asapBanner.sub}</div>
            </div>
          )}

          <div className="label">{status === "assigned" ? "Your worker" : "Done by"}</div>
          <WorkerCard
            name={assignment.worker.name}
            meta={isAsap ? workerMeta : `${titleCase(assignment.worker.trade)} · ${assignment.worker.rating ? `rated ${Number(assignment.worker.rating).toFixed(1)}` : "new member"}`}
            score={assignment.score}
            breakdown={assignment.score_breakdown}
            explanation={assignment.explanation}
          />
          {status === "assigned" && (
            <div className="job-actions">
              <a href={assignment.worker.phone ? `tel:${assignment.worker.phone}` : undefined} className={assignment.worker.phone ? "" : "disabled"}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" />
                </svg>
                {assignment.worker.phone ? `Call ${assignment.worker.name.split(" ")[0]}` : "No number yet"}
              </a>
              <Link to="/ghar/home" className="">
                <ArrowRight size={20} />
                Book another
              </Link>
            </div>
          )}
          {status === "assigned" && !settlement && (
            <div className="card soft stack" style={{ gap: 4 }}>
              <div style={{ fontWeight: 700 }}>How the price works</div>
              <div className="small muted">
                When the job ends {assignment.worker.name.split(" ")[0]} enters the hours and materials; the community rate card prices it and you'll be asked to agree here. You pay them directly — cash or UPI. Nothing is charged through the app.
              </div>
              <RateHint trade={booking.trade} compact />
            </div>
          )}
        </section>
      )}

      {settlement && (
        <section className="stack">
          <div className="label">{settlement.status === "agreed" ? "Your payment" : "Price on the table"}</div>
          <SettlementCard settlement={settlement} role="customer" onChange={load} />
        </section>
      )}

      {status === "completed" && !settlement && payment_ledger.length > 0 && (
        <section className="stack">
          <div className="label">Your payment</div>
          <div className="card stack" style={{ gap: 8 }}>
            <div className="row between">
              <div style={{ fontWeight: 700 }}>Bill</div>
              <div className="display num" style={{ fontSize: 22, fontWeight: 700 }}>
                {formatRupees(payment_ledger.reduce((sum, e) => sum + e.amount_rupees, 0))}
              </div>
            </div>
            <div className="split">
              {payment_ledger.map((e, i) => (
                <div key={e.party} style={{ width: `${e.share_percent}%`, background: ["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)"][i] }} />
              ))}
            </div>
            {payment_ledger.map((e, i) => (
              <div className="row small" key={e.party}>
                <span className="swatch" style={{ background: ["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)"][i] }} />
                <span className="grow">{{ worker: "To your worker", welfare_fund: "Workers' welfare fund", platform_operations: "Platform operations" }[e.party]}</span>
                <span className="num" style={{ fontWeight: 700 }}>{formatRupees(e.amount_rupees)}</span>
                <span className="num muted" style={{ width: 36, textAlign: "right" }}>{e.share_percent}%</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {status === "completed" && !rating && <RatingForm bookingId={bookingId} onRated={load} />}
      {rating && (
        <section className="card row" style={{ gap: 12 }}>
          <span className="dot green">
            <Check size={16} />
          </span>
          <div className="stack" style={{ gap: 2 }}>
            <div style={{ fontWeight: 700 }}>You rated this job {rating.rating}/5</div>
            {rating.comment && <div className="small muted">“{rating.comment}”</div>}
          </div>
        </section>
      )}

      <Link to="/ghar/home" className="btn outline">
        Book another service
      </Link>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const kind = status === "completed" ? "green" : status === "assigned" ? "terracotta" : "grey";
  const text = status === "pending" ? "Finding a worker" : status === "assigned" ? "Worker assigned" : status === "cancelled" ? "Cancelled" : titleCase(status);
  return <span className={`pill ${kind}`}>{text}</span>;
}

function WorkerCard({
  name,
  meta,
  score,
  breakdown,
  explanation,
}: {
  name: string;
  meta: string;
  score: number | null;
  breakdown: Record<string, number> | null;
  explanation: string | null;
}) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="card stack" style={{ gap: 10 }}>
      <div className="row" style={{ gap: 12 }}>
        <span className="avatar">{initials}</span>
        <div className="grow stack" style={{ gap: 1 }}>
          <div style={{ fontWeight: 700 }}>{name}</div>
          <div className="small muted">{meta}</div>
        </div>
        {score !== null && (
          <div className="display num" style={{ fontSize: 20, fontWeight: 700, color: "var(--green-d)" }}>
            {score.toFixed(2)}
          </div>
        )}
      </div>
      {breakdown && (
        <div className="grid-2" style={{ gap: 6 }}>
          {Object.entries(breakdown).map(([factor, value]) => (
            <div key={factor} className="stack" style={{ gap: 3 }}>
              <div className="row between tiny">
                <span className="muted">{titleCase(factor)}</span>
                <span className="num" style={{ fontWeight: 700 }}>
                  {Math.round(value * 100)}%
                </span>
              </div>
              <div className="bar thin">
                <div style={{ width: `${Math.round(value * 100)}%`, background: "var(--accent)" }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {explanation && <div className="small" style={{ color: "var(--ink-2)" }}>{explanation}</div>}
    </div>
  );
}

function RatingForm({ bookingId, onRated }: { bookingId: number; onRated: () => void }) {
  const [stars, setStars] = useState(0);
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
      <div className="label">How did it go?</div>
      <div className="card stack">
        <div className="row" style={{ gap: 4 }} role="radiogroup" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              type="button"
              key={n}
              onClick={() => setStars(n)}
              role="radio"
              aria-checked={stars === n}
              aria-label={`${n} star${n > 1 ? "s" : ""}`}
              style={{ background: "none", border: 0, padding: 6, color: n <= stars ? "var(--accent)" : "var(--line)" }}
            >
              <Star size={30} filled={n <= stars} />
            </button>
          ))}
        </div>
        <label className="field">
          <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="A word for the cooperative (optional)" maxLength={500} />
        </label>
        {error && <div className="notice error">{error}</div>}
        <button type="button" className="btn green" disabled={stars === 0 || busy} onClick={submit}>
          {busy ? "Saving…" : "Submit rating"}
        </button>
      </div>
    </section>
  );
}
