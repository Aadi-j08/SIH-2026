import { useEffect, useRef, useState, type FormEvent } from "react";

import { api, describeWindow, errorMessage, storageGet, storageSet, type VoiceParse, type Worker as WorkerT } from "../api";
import { Check, Cross, Mic, Waveform } from "./Icons";
import { listenOnce, speechSupported, type Listener } from "../lib/speech";

const LANG_KEY = "sahakarsetu.voiceLang";

/**
 * Speak (or type) an availability sentence, see what the parser understood —
 * including what it had to guess — and save it to the worker's windows.
 * `compact` renders the one-line dark card that expands on tap (Kaam home).
 */
export default function VoiceAvailability({ worker, onSaved, compact = false }: { worker: WorkerT; onSaved: (w: WorkerT) => void; compact?: boolean }) {
  const supported = speechSupported();
  const [open, setOpen] = useState(() => !compact || window.location.hash === "#voice");
  const [lang, setLang] = useState<string>(() => storageGet(LANG_KEY) ?? "hi-IN");
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [parsed, setParsed] = useState<VoiceParse | null>(null);
  const [replace, setReplace] = useState(false);
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
    setOpen(true);
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

  // Compatibility fallback for a cached API response that predates the
  // confidence fields. The updated backend still remains authoritative.
  const canSave = parsed ? (parsed.can_save ?? (parsed.windows.length > 0 && parsed.confidence >= 0.5)) : false;
  const needsConfirmation = parsed?.requires_confirmation ?? false;

  const save = async () => {
    if (!parsed?.windows.length || !canSave) return;
    const confirmed = needsConfirmation
      ? window.confirm(parsed.confirmation_message ?? "Please confirm the interpreted availability.")
      : true;
    if (!confirmed) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.workers.setAvailabilityByVoice(worker.id, parsed.transcript, replace, undefined, true);
      onSaved(result.worker);
      setParsed(null);
      setTranscript("");
      setMessage({ kind: "info", text: `Saved. ${result.parsed.summary}` });
      if (compact) setOpen(false);
    } catch (e) {
      setMessage({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  const guessed = (parsed?.assumptions?.length ?? 0) > 0;

  return (
    <section className="stack" id="voice">
      {compact && !open ? (
        <button type="button" className="card dark voice-compact" onClick={() => setOpen(true)}>
          <span className="mic mic-small" aria-hidden="true">
            <Mic size={24} />
          </span>
          <span className="stack grow" style={{ gap: 2, textAlign: "left" }}>
            <span className="display" style={{ fontSize: 17, fontWeight: 700 }}>Change your week by voice</span>
            <span className="hi" style={{ fontSize: 14, color: "var(--ink-on-dark)" }}>बोलिए — “रविवार को खाली हूँ”</span>
          </span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--ink-on-dark)" }}>
            <path d="M9 6l6 6-6 6" />
          </svg>
        </button>
      ) : (
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
          {compact && (
            <button type="button" className="back" style={{ color: "var(--ink-on-dark)", minHeight: 32 }} onClick={() => { setOpen(false); setParsed(null); setTranscript(""); }}>
              Close
            </button>
          )}
        </div>
      )}

      {open && (
        <form className="field" onSubmit={submitTyped}>
          <Waveform size={18} style={{ color: "var(--ink-3)" }} />
          <input value={transcript} onChange={(e) => setTranscript(e.target.value)} placeholder="…or type it: kal subah free hoon" aria-label="Availability sentence" />
          <button type="submit" className="adorn" disabled={busy || !transcript.trim()}>
            Understand
          </button>
        </form>
      )}

      {message && <div className={`notice ${message.kind}`}>{message.text}</div>}

      {parsed && parsed.windows.length > 0 && (
        <div className="stack">
          <div className="row between">
            <div className="label">Understood as</div>
            <div className="tiny muted">
              {parsed.language === "hi" ? "Hindi" : parsed.language === "en" ? "English" : parsed.language === "mixed" ? "Hinglish" : ""} · {Math.round(parsed.confidence * 100)}% sure
            </div>
          </div>
          {needsConfirmation && canSave && (
            <div className="notice info">This interpretation is uncertain. Check the schedule carefully before confirming.</div>
          )}
          {!canSave && <div className="notice error">I could not understand this reliably. Please include a day and time and try again.</div>}
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
          {guessed && (
            <div className="notice warn stack" style={{ gap: 4 }}>
              <div style={{ fontWeight: 700 }}>I had to guess — check before saving</div>
              {(parsed.assumptions ?? []).map((a) => (
                <div key={a} className="small">{a}</div>
              ))}
            </div>
          )}
          <label className="row tiny muted" style={{ gap: 8 }}>
            <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
            Replace everything I've saved ({worker.availability.length} window{worker.availability.length === 1 ? "" : "s"}) instead of adding to it
          </label>
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className={`btn grow ${guessed || needsConfirmation ? "outline" : "green"}`} onClick={save} disabled={busy || !canSave}>
              {busy ? "Saving…" : needsConfirmation ? "Confirm & save" : guessed ? "Save anyway" : "Save availability"}
            </button>
            <button type="button" className={`btn ${guessed ? "green" : "outline"}`} onClick={() => { setParsed(null); setTranscript(""); }} disabled={busy}>
              Say again
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
