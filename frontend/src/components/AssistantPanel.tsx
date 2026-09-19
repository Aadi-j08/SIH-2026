import { useEffect, useRef, useState, type FormEvent } from "react";

import { api, errorMessage, type AssistantResponse } from "../api";
import { Mic } from "./Icons";
import { listenOnce, speechSupported, type Listener } from "../lib/speech";

type AssistantRole = "customer" | "worker" | "council";

type Props = {
  role: AssistantRole;
  latitude?: number;
  longitude?: number;
  onBooking?: (id: number) => void;
};

export default function AssistantPanel({ role, latitude, longitude, onBooking }: Props) {
  const placeholder = role === "customer" ? "Try: book plumbing tomorrow at 10" : role === "worker" ? "Try: show my jobs or accept booking 4" : "Try: forecast plumbing demand";
  const [transcript, setTranscript] = useState("");
  const [response, setResponse] = useState<AssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const listener = useRef<Listener | null>(null);
  const supported = speechSupported();

  useEffect(() => () => listener.current?.stop(), []);

  const send = async (confirmed = false, textOverride?: string) => {
    const text = (textOverride ?? transcript).trim();
    if (!text) return;
    setLoading(true);
    setError(null);
    try {
      const next = await api.assistant.voice({ transcript: text, confirmed, latitude, longitude });
      setResponse(next);
      const result = next.result as { booking?: { id?: number } } | null;
      if (result?.booking?.id && onBooking) onBooking(result.booking.id);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void send();
  };

  const toggleListening = () => {
    if (listening) {
      listener.current?.stop();
      return;
    }
    setError(null);
    const started = listenOnce("hi-IN", {
      onInterim: setTranscript,
      onFinal: (text) => {
        setTranscript(text);
        void send(false, text);
      },
      onError: setError,
      onEnd: () => setListening(false),
    });
    if (started) {
      listener.current = started;
      setListening(true);
    }
  };

  return (
    <section className="stack assistant-panel" aria-labelledby="assistant-heading">
      <div className="row between">
        <div className="stack" style={{ gap: 2 }}>
          <div className="label" id="assistant-heading">Speak or type</div>
          <div className="tiny muted">English · हिंदी · Hinglish</div>
        </div>
        <button type="button" className={`btn small ${listening ? "primary" : "outline"}`} onClick={toggleListening} disabled={!supported || loading} aria-pressed={listening}>
          <Mic size={16} /> {listening ? "Stop" : "Speak"}
        </button>
      </div>
      <form className="field" onSubmit={submit}>
        <input value={transcript} onChange={(event) => setTranscript(event.target.value)} placeholder={placeholder} aria-label="Assistant message" />
        <button type="submit" className="adorn" disabled={loading || !transcript.trim()}>{loading ? "…" : "Ask"}</button>
      </form>
      {!supported && <div className="tiny muted">Voice recognition is unavailable here. Type your request instead.</div>}
      {error && <div className="notice error">{error} <button type="button" className="link" onClick={() => void send()}>Retry</button></div>}
      {response && (
        <div className="card soft stack" style={{ gap: 8 }}>
          <div className="small">{response.reply}</div>
          <div className="tiny muted">Heard: “{response.transcript}” · {response.language} · {Math.round(response.confidence * 100)}%</div>
          {Object.keys(response.action_preview).length > 0 && <pre className="tiny" style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(response.action_preview, null, 2)}</pre>}
          {response.requires_confirmation && (
            <button type="button" className="btn primary" onClick={() => void send(true)} disabled={loading}>
              {loading ? "Confirming…" : response.confirmation_message ?? "Confirm action"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
