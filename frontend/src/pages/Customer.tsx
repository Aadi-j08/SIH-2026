import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  DEFAULT_LOCATION,
  TRADES,
  api,
  errorMessage,
  formatRupees,
  formatWhen,
  titleCase,
  storageGet,
  storageSet,
  type BookingDetail,
} from "../api";
import { useAuth } from "../lib/auth";
import { ArrowRight, Check, Clock, Locate, Pin, Star, TRADE_ICONS } from "../components/Icons";

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
    <form className="page" onSubmit={submit}>
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
          No advance payment. Pay after the job — 10% goes to the workers' welfare fund.
        </div>
      </div>
    </form>
  );
}

// ── booking status ───────────────────────────────────────────────────

function BookingStatus({ bookingId }: { bookingId: number }) {
  const [detail, setDetail] = useState<BookingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const next = await api.bookings.detail(bookingId);
      setDetail(next);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId]);

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
  const IconFor = TRADE_ICONS[booking.trade] ?? TRADE_ICONS.plumbing;

  return (
    <div className="page">
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
          <div className="label">{status === "assigned" ? "Your worker" : "Done by"}</div>
          <WorkerCard
            name={assignment.worker.name}
            meta={`${titleCase(assignment.worker.trade)} · ${assignment.worker.rating ? `rated ${Number(assignment.worker.rating).toFixed(1)}` : "new member"}`}
            score={assignment.score}
            breakdown={assignment.score_breakdown}
            explanation={assignment.explanation}
          />
        </section>
      )}

      {status === "completed" && payment_ledger.length > 0 && (
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
  const text = status === "pending" ? "Finding a worker" : status === "assigned" ? "Worker assigned" : titleCase(status);
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
