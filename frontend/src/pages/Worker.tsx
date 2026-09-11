import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  api,
  describeWindow,
  errorMessage,
  formatRupees,
  formatWhen,
  storageGet,
  storageSet,
  titleCase,
  type BookingDetail,
  type DashboardWorker,
  type VoiceParse,
  type Worker as WorkerT,
} from "../api";
import { Check, Cross, Mic, Waveform } from "../components/Icons";
import { useAuth } from "../lib/auth";
import { listenOnce, speechSupported, type Listener } from "../lib/speech";

const LANG_KEY = "sahakarsetu.voiceLang";

export default function Worker() {
  const { user } = useAuth();
  const [worker, setWorker] = useState<WorkerT | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.worker_id) {
      setError("This Kaam account is not linked to a worker record. Ask the cooperative to fix it.");
      return;
    }
    api.workers.get(user.worker_id).then(setWorker).catch((e) => setError(errorMessage(e)));
  }, [user?.worker_id]);

  if (error) return <div className="page notice error">{error}</div>;
  if (!worker) return <div className="page muted">Loading…</div>;

  return (
    <div className="page">
      <Greeting worker={worker} />
      <VoiceAvailability worker={worker} onSaved={setWorker} />
      <TodaysJob worker={worker} />
      <ThisWeek worker={worker} />
    </div>
  );
}

// ── greeting ─────────────────────────────────────────────────────────

function Greeting({ worker }: { worker: WorkerT }) {
  const initials = worker.name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className="row between">
      <div className="stack" style={{ gap: 3 }}>
        <div className="row" style={{ alignItems: "baseline", gap: 8 }}>
          <span className="hi" style={{ fontSize: 22, fontWeight: 600 }}>नमस्ते,</span>
          <span className="display" style={{ fontSize: 24, fontWeight: 700 }}>{worker.name.split(" ")[0]}</span>
        </div>
        <div className="small muted">{titleCase(worker.trade)} · Cooperative member</div>
      </div>
      <span className="avatar">{initials}</span>
    </div>
  );
}

// ── voice availability ───────────────────────────────────────────────

function VoiceAvailability({ worker, onSaved }: { worker: WorkerT; onSaved: (w: WorkerT) => void }) {
  const supported = speechSupported();
  const [lang, setLang] = useState<string>(() => storageGet(LANG_KEY) ?? "hi-IN");
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [parsed, setParsed] = useState<VoiceParse | null>(null);
  const [replace, setReplace] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const listener = useRef<Listener | null>(null);

  useEffect(() => storageSet(LANG_KEY, lang), [lang]);
  useEffect(() => () => listener.current?.stop(), []);

  const parse = async (text: string) => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.voice.parse(text);
      setParsed(result);
      if (!result.windows.length) setMessage({ kind: "info", text: "Couldn't find a day or time in that — try “kal subah free hoon” or “busy on Sunday”." });
    } catch (e) {
      setMessage({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  const toggleMic = () => {
    if (listening) {
      listener.current?.stop();
      return;
    }
    setParsed(null);
    setTranscript("");
    setMessage(null);
    const started = listenOnce(lang, {
      onInterim: setTranscript,
      onFinal: (text) => {
        setTranscript(text);
        void parse(text);
      },
      onError: (text) => setMessage({ kind: "error", text }),
      onEnd: () => setListening(false),
    });
    if (started) {
      listener.current = started;
      setListening(true);
    }
  };

  const submitTyped = (event: FormEvent) => {
    event.preventDefault();
    if (transcript.trim()) void parse(transcript.trim());
  };

  const save = async () => {
    if (!parsed?.windows.length) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.workers.setAvailabilityByVoice(worker.id, parsed.transcript, replace);
      onSaved(result.worker);
      setParsed(null);
      setTranscript("");
      setMessage({ kind: "info", text: `Saved. ${result.parsed.summary}` });
    } catch (e) {
      setMessage({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="stack">
      <div className="card dark" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, padding: "16px 20px 14px", borderRadius: "var(--radius-xl)" }}>
        <div className="stack" style={{ alignItems: "center", gap: 4 }}>
          <div className="display" style={{ fontSize: 18, fontWeight: 700 }}>When are you free?</div>
          <div className="hi" style={{ fontSize: 15, color: "var(--ink-on-dark)" }}>बोलिए — आप कब खाली हैं?</div>
        </div>
        <div className={`mic-wrap${listening ? " listening" : ""}`}>
          <div className="mic-pulse" />
          <button type="button" className="mic" onClick={toggleMic} disabled={!supported || busy} aria-pressed={listening} aria-label={listening ? "Stop listening" : "Start speaking"}>
            <Mic size={30} />
          </button>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <div className="seg" style={{ borderColor: "#4a403a" }}>
            {[
              ["hi-IN", "हिंदी"],
              ["en-IN", "English"],
            ].map(([code, label]) => (
              <a key={code} href="#" className={lang === code ? "active" : ""} style={{ color: lang === code ? undefined : "var(--ink-on-dark)", height: 28, fontSize: 12 }} onClick={(e) => { e.preventDefault(); setLang(code); }}>
                {label}
              </a>
            ))}
          </div>
          <div className="tiny" style={{ color: "var(--ink-on-dark)", letterSpacing: "0.04em" }}>
            {supported ? (listening ? "LISTENING… TAP TO STOP" : "TAP AND SPEAK") : "TYPE BELOW — THIS BROWSER CAN'T LISTEN"}
          </div>
        </div>
      </div>

      <form className="field" onSubmit={submitTyped}>
        <Waveform size={18} style={{ color: "var(--ink-3)" }} />
        <input value={transcript} onChange={(e) => setTranscript(e.target.value)} placeholder="…or type it: kal subah free hoon" aria-label="Availability sentence" />
        <button type="submit" className="adorn" disabled={busy || !transcript.trim()}>
          Understand
        </button>
      </form>

      {message && <div className={`notice ${message.kind}`}>{message.text}</div>}

      {parsed && parsed.windows.length > 0 && (
        <div className="stack">
          <div className="row between">
            <div className="label">Understood as</div>
            <div className="tiny muted">
              {parsed.language === "hi" ? "Hindi" : parsed.language === "en" ? "English" : parsed.language === "mixed" ? "Hinglish" : ""} · {Math.round(parsed.confidence * 100)}% sure
            </div>
          </div>
          {parsed.windows.map((w, i) => (
            <div className="card row" key={i} style={{ gap: 12, padding: "6px 12px", minHeight: 48 }}>
              <span className={`dot ${w.available ? "green" : "grey"}`}>{w.available ? <Check size={16} /> : <Cross size={16} />}</span>
              <div className="stack" style={{ gap: 1 }}>
                <div style={{ fontWeight: 700, color: w.available ? "var(--green-d)" : "var(--ink-2)" }}>{describeWindow(w)}</div>
                <div className="small muted num">
                  {w.start} – {w.end}
                </div>
              </div>
            </div>
          ))}
          <label className="row tiny muted" style={{ gap: 8 }}>
            <input type="checkbox" checked={!replace} onChange={(e) => setReplace(!e.target.checked)} />
            Add to what I've already saved ({worker.availability.length} window{worker.availability.length === 1 ? "" : "s"})
          </label>
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn green grow" onClick={save} disabled={busy}>
              {busy ? "Saving…" : "Save availability"}
            </button>
            <button type="button" className="btn outline" onClick={() => { setParsed(null); setTranscript(""); }} disabled={busy}>
              Say again
            </button>
          </div>
        </div>
      )}

      {!parsed && worker.availability.length > 0 && (
        <details className="card soft small">
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Saved availability ({worker.availability.length})</summary>
          <div className="stack" style={{ gap: 4, marginTop: 8 }}>
            {worker.availability.map((w, i) => (
              <div key={i} className="row between">
                <span>{describeWindow(w)}</span>
                <span className="num muted">
                  {w.start} – {w.end}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

// ── today's job ──────────────────────────────────────────────────────

function TodaysJob({ worker }: { worker: WorkerT }) {
  const [jobs, setJobs] = useState<BookingDetail[] | null>(null);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const assigned = await api.bookings.list({ status: "assigned" });
      const details = await Promise.all(assigned.map((b) => api.bookings.detail(b.id)));
      setJobs(details.filter((d) => d.assignment?.worker.id === worker.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 6000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [worker.id]);

  const complete = async (bookingId: number) => {
    const value = Number(amount);
    if (!(value > 0)) {
      setError("Enter the bill amount in rupees.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.bookings.complete(bookingId, value);
      setAmount("");
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="stack">
      <div className="label">Your jobs</div>
      {error && <div className="notice error">{error}</div>}
      {jobs === null ? (
        <div className="small muted">Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="card soft small muted">Nothing assigned right now. Keep your availability up to date and the engine will send work your way.</div>
      ) : (
        jobs.map(({ booking, assignment }) => (
          <div className="card stack" key={booking.id} style={{ gap: 8 }}>
            <div className="stack" style={{ gap: 3 }}>
              <div style={{ fontWeight: 700 }}>
                {booking.customer_name} · {titleCase(booking.trade)}
              </div>
              <div className="small muted">
                {formatWhen(booking.scheduled_for)}
                {booking.address ? ` · ${booking.address}` : ""}
                {booking.customer_phone ? ` · ${booking.customer_phone}` : ""}
              </div>
              {assignment?.explanation && <span className="pill green" style={{ alignSelf: "flex-start" }}>Why you: {assignment.explanation.split(";")[1]?.trim().replace(/\s*\(.*\)/, "") ?? "engine's top pick"}</span>}
            </div>
            <div className="row" style={{ gap: 8 }}>
              <label className="field grow" style={{ minHeight: 44 }}>
                <span className="muted">₹</span>
                <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Bill amount" aria-label="Bill amount in rupees" style={{ height: 40 }} />
              </label>
              <button type="button" className="btn green" style={{ minHeight: 44, fontSize: 14 }} disabled={busy} onClick={() => complete(booking.id)}>
                Job done
              </button>
            </div>
          </div>
        ))
      )}
    </section>
  );
}

// ── this week ────────────────────────────────────────────────────────

function ThisWeek({ worker }: { worker: WorkerT }) {
  const [stats, setStats] = useState<DashboardWorker | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api.admin
        .dashboard()
        .then((d) => {
          if (!cancelled) setStats(d.workers.find((w) => w.id === worker.id) ?? null);
        })
        .catch(() => undefined);
    void load();
    const timer = window.setInterval(load, 6000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [worker.id]);

  const days = stats?.engagement_days ?? 0;
  return (
    <section className="grid-3" style={{ gap: 8 }}>
      <div className="stat">
        <div className="value num">{stats?.jobs_this_week ?? worker.jobs_this_week}</div>
        <div className="caption">jobs this week</div>
      </div>
      <div className="stat">
        <div className="value num">{formatRupees(stats?.earnings_rupees ?? 0)}</div>
        <div className="caption">earned</div>
      </div>
      <div className="stat" style={{ gap: 6 }}>
        <div className="value num">
          {days}
          <small> / 90</small>
        </div>
        <div className="stack" style={{ gap: 4 }}>
          <div className="bar thin">
            <div style={{ width: `${Math.min(100, Math.round((days / 90) * 100))}%` }} />
          </div>
          <div className="caption" style={{ fontSize: 11, lineHeight: 1.2 }}>
            days to benefits
          </div>
        </div>
      </div>
    </section>
  );
}
