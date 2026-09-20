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
import { ArrowRight, Clock, Locate, Pin, TRADE_ICONS } from "../components/Icons";
import { RateHint } from "../components/Settlement";
import AssistantPanel from "../components/AssistantPanel";
import { AIVoiceSearchBar } from "../components/AIVoiceSearchBar";
import { LiveBookingTracker } from "../components/LiveBookingTracker";

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

  return (
    <div className="page" style={{ maxWidth: 640, margin: "0 auto", paddingBottom: 60 }}>
      <LiveBookingTracker detail={detail} settlement={settlement} onRefresh={load} />
    </div>
  );
}
