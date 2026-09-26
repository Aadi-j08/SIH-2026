import { useRef, useState } from "react";
import { api } from "../api";

interface AIVoiceSearchBarProps {
  onSelectTrade?: (trade: string) => void;
  onSelectUrgency?: (urgency: string) => void;
}

export function AIVoiceSearchBar({ onSelectTrade, onSelectUrgency }: AIVoiceSearchBarProps) {
  const [query, setQuery] = useState("");
  const [transcript, setTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [aiResult, setAiResult] = useState<any>(null);
  const recognitionRef = useRef<any>(null);

  const handleSpeech = () => {
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      setIsListening(false);
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice recognition is not supported in this browser. Please type your query.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "hi-IN"; // Hindi / Indian English
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      setIsListening(true);
      setTranscript("");
      setAiResult(null);
    };
    recognition.onerror = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    let latestCaptured = "";
    let parsed = false;

    recognition.onresult = (event: any) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        const text = item[0]?.transcript || "";
        if (item.isFinal) {
          final += text;
        } else {
          interim += text;
        }
      }
      const captured = (final || interim || (event.results[0] && event.results[0][0]?.transcript) || "").trim();
      if (captured) {
        latestCaptured = captured;
        setTranscript(captured);
        setQuery(captured);
      }
      if (final.trim() && !parsed) {
        parsed = true;
        handleAIParse(final.trim());
      }
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
      if (!parsed && latestCaptured.trim()) {
        parsed = true;
        handleAIParse(latestCaptured.trim());
      }
    };

    recognition.start();
  };

  const handleAIParse = async (textToParse?: string) => {
    const text = textToParse || query;
    if (!text.trim()) return;

    setLoading(true);
    try {
      const res = await api.assistant.parseQuery(text, "hi");
      setAiResult(res);
      if (res.trade && res.trade !== "general" && onSelectTrade) {
        onSelectTrade(res.trade);
      }
      if (res.urgency && onSelectUrgency) {
        onSelectUrgency(res.urgency);
      }
    } catch (err) {
      console.error("AI Parse failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(198, 93, 38, 0.08), rgba(94, 120, 217, 0.08))",
      border: "1px solid rgba(198, 93, 38, 0.25)",
      borderRadius: "16px",
      padding: "18px 20px",
      marginBottom: "24px",
      boxShadow: "0 4px 20px rgba(0,0,0,0.03)"
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "1.2rem" }}>✨</span>
          <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--terracotta-d, #C65D26)", letterSpacing: "0.02em" }}>
            AI SMART VOICE ASSISTANT
          </span>
        </div>
        <span style={{ fontSize: "0.75rem", background: "rgba(37, 152, 77, 0.12)", color: "#1b7337", padding: "3px 8px", borderRadius: "12px", fontWeight: 600 }}>
          Hindi • Hinglish • English
        </span>
      </div>

      <p style={{ margin: "0 0 12px 0", fontSize: "0.85rem", color: "#666" }}>
        Speak or type naturally in Hindi/English (e.g. <i>"Ghar me tap leak ho raha hai plumber chahiye"</i>)
      </p>

      <div style={{ display: "flex", gap: "8px" }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAIParse()}
          placeholder="Speak or describe what you need help with..."
          style={{
            flex: 1,
            padding: "12px 16px",
            borderRadius: "10px",
            border: "1px solid #dcd6ce",
            background: "#fff",
            fontSize: "0.92rem",
            outline: "none"
          }}
        />

        <button
          type="button"
          onClick={handleSpeech}
          style={{
            padding: "10px 18px",
            borderRadius: "10px",
            background: isListening ? "#dc2626" : "var(--terracotta, #C65D26)",
            color: "#fff",
            border: "none",
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            transition: "all 0.2s ease"
          }}
        >
          {isListening ? "🔴 Listening..." : "🎙️ Speak"}
        </button>

        <button
          type="button"
          onClick={() => handleAIParse()}
          disabled={loading}
          style={{
            padding: "10px 18px",
            borderRadius: "10px",
            background: "var(--indigo, #5E78D9)",
            color: "#fff",
            border: "none",
            fontWeight: 600,
            cursor: "pointer"
          }}
        >
          {loading ? "Analyzing..." : "🔍 Find"}
        </button>
      </div>

      {/* Real Live / Final STT Transcript */}
      {transcript ? (
        <div style={{
          marginTop: "12px",
          padding: "10px 14px",
          background: "#fff",
          borderRadius: "10px",
          border: "1px solid #dcd6ce",
          fontSize: "0.9rem",
          display: "flex",
          alignItems: "center",
          gap: "10px"
        }}>
          <span style={{ fontSize: "1.1rem" }}>💬</span>
          <div style={{ flex: 1 }}>
            <span style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              fontWeight: 700,
              color: isListening ? "#dc2626" : "#777",
              letterSpacing: "0.04em",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              marginBottom: "2px"
            }}>
              {isListening ? (
                <>
                  <span style={{
                    display: "inline-block",
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: "#dc2626"
                  }} />
                  Live Transcript
                </>
              ) : (
                "Transcribed Speech"
              )}
            </span>
            <span style={{ fontWeight: 600, color: "#1f2937" }}>“{transcript}”</span>
          </div>
          {isListening && (
            <span style={{
              fontSize: "0.72rem",
              color: "#dc2626",
              fontWeight: 700,
              padding: "2px 8px",
              background: "rgba(220, 38, 38, 0.1)",
              borderRadius: "6px"
            }}>
              LIVE
            </span>
          )}
        </div>
      ) : isListening ? (
        <div style={{
          marginTop: "12px",
          padding: "10px 14px",
          background: "rgba(220, 38, 38, 0.05)",
          borderRadius: "10px",
          border: "1px dashed rgba(220, 38, 38, 0.35)",
          fontSize: "0.86rem",
          color: "#b91c1c",
          display: "flex",
          alignItems: "center",
          gap: "8px"
        }}>
          <span>🎙️</span>
          <span>Listening… Speak clearly into your microphone</span>
        </div>
      ) : null}

      {aiResult && (
        <div style={{
          marginTop: "14px",
          padding: "12px 14px",
          background: "#fff",
          borderRadius: "10px",
          border: "1px solid #e5e0d8",
          fontSize: "0.85rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "10px"
        }}>
          <div>
            <strong>🤖 AI Extracted:</strong> Trade: <span style={{ color: "var(--terracotta-d)", fontWeight: 700, textTransform: "capitalize" }}>{aiResult.trade}</span> · Urgency: <span style={{ textTransform: "capitalize", fontWeight: 600 }}>{aiResult.urgency}</span>
            {aiResult.preferred_time && <span> · Slot: <b>{aiResult.preferred_time}</b></span>}
          </div>
          <span style={{ fontSize: "0.75rem", color: "#888" }}>
            Powered by {aiResult.source === "gemini_1.5_flash" ? "Google Gemini 1.5 Flash" : "Offline NLP Fallback"}
          </span>
        </div>
      )}
    </div>
  );
}
