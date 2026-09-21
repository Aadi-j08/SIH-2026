/**
 * Speech Recognition (STT) and Speech Synthesis (TTS) module for SahakarSetu.
 * Supports Hindi (hi-IN) and English (en-IN).
 */

// ── Speech Recognition (STT) ────────────────────────────────────────────────

export interface Listener {
  stop: () => void;
}

export interface SpeechCallbacks {
  onInterim?: (text: string) => void;
  onFinal?: (text: string) => void;
  onError?: (errorText: string) => void;
  onEnd?: () => void;
}

export function speechSupported(): boolean {
  if (typeof window === "undefined") return false;
  return "SpeechRecognition" in window || "webkitSpeechRecognition" in window;
}

export function listenOnce(lang: string, callbacks: SpeechCallbacks): Listener | null {
  if (!speechSupported()) {
    callbacks.onError?.("Speech recognition is not supported in this browser.");
    return null;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognition: any = new SpeechRec();

  recognition.lang = lang || "hi-IN";
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.continuous = false;

  let finalTranscript = "";

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  recognition.onresult = (event: any) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const trans = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += trans;
      } else {
        interim += trans;
      }
    }
    if (interim && callbacks.onInterim) {
      callbacks.onInterim(interim);
    }
    if (finalTranscript && callbacks.onFinal) {
      callbacks.onFinal(finalTranscript.trim());
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  recognition.onerror = (event: any) => {
    callbacks.onError?.(event.error || "Speech recognition error");
  };

  recognition.onend = () => {
    callbacks.onEnd?.();
  };

  try {
    recognition.start();
  } catch (err) {
    callbacks.onError?.(String(err));
    return null;
  }

  return {
    stop: () => {
      try {
        recognition.stop();
      } catch {
        // ignore
      }
    },
  };
}

// ── Speech Synthesis (TTS) ──────────────────────────────────────────────────

const HINDI_TRADES: Record<string, string> = {
  plumbing: "नल और पाइप का काम",
  electrical: "बिजली और वायरिंग का काम",
  carpentry: "बढ़ई और लकड़ी का काम",
  painting: "रंगाई और पुट्टी का काम",
  cleaning: "सफाई का काम",
};

export function isSpeechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

export function stopSpeaking(): void {
  if (isSpeechSupported()) {
    window.speechSynthesis.cancel();
  }
}

export function speakText(
  text: string,
  lang: "hi-IN" | "en-IN" = "hi-IN",
  onEnd?: () => void,
  onError?: () => void
): void {
  if (!isSpeechSupported()) {
    if (onError) onError();
    return;
  }

  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = 0.95;
  utterance.pitch = 1.0;

  const voices = window.speechSynthesis.getVoices();
  const hindiVoice = voices.find((v) => v.lang.startsWith("hi") || v.name.toLowerCase().includes("hindi"));
  if (hindiVoice && lang === "hi-IN") {
    utterance.voice = hindiVoice;
  }

  utterance.onend = () => {
    if (onEnd) onEnd();
  };

  utterance.onerror = () => {
    if (onError) onError();
  };

  window.speechSynthesis.speak(utterance);
}

export function speakJobSummary(
  job: {
    trade: string;
    customer_name: string;
    address: string | null;
    locality?: string | null;
    is_urgent?: boolean;
    urgency_level?: string;
  },
  onEnd?: () => void,
  onError?: () => void
): void {
  const tradeHindi = HINDI_TRADES[job.trade.toLowerCase()] || job.trade;
  const isUrgent = job.is_urgent || job.urgency_level === "urgent" || job.urgency_level === "high";

  const urgentPrefix = isUrgent ? "सावधान! यह तत्काल इमरजेंसी काम है। " : "";
  const addressText = job.address || job.locality || "पता उपलब्ध नहीं है";

  const message = `${urgentPrefix}नया काम: ${tradeHindi}। ग्राहक का नाम: ${job.customer_name}। पता: ${addressText}। स्वीकार करने के लिए नीचे हरा बटन दबाएं।`;

  speakText(message, "hi-IN", onEnd, onError);
}
