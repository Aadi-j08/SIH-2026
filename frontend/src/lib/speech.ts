/**
 * Thin wrapper over the browser's Web Speech API. Speech-to-text happens on
 * the device; the transcript goes to the backend's voice parser. Returns
 * null when the browser has no recognition support (then the UI falls back
 * to typing).
 */

type RecognitionCtor = new () => SpeechRecognitionLike;

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

function recognitionClass(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const speechSupported = (): boolean => recognitionClass() !== null;

export type Listener = {
  stop: () => void;
};

/**
 * Listen once and resolve with the best transcript. `lang` is a BCP-47 tag:
 * "hi-IN" understands Hindi and most Hinglish, "en-IN" Indian English.
 */
export function listenOnce(
  lang: string,
  handlers: { onInterim?: (text: string) => void; onFinal: (text: string) => void; onError: (message: string) => void; onEnd?: () => void },
): Listener | null {
  const Ctor = recognitionClass();
  if (!Ctor) return null;
  const recognition = new Ctor();
  recognition.lang = lang;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.continuous = false;

  let finalText = "";
  recognition.onresult = (event) => {
    let interim = "";
    for (let i = 0; i < event.results.length; i += 1) {
      const result = event.results[i] as ArrayLike<{ transcript: string }> & { isFinal?: boolean };
      const text = result[0]?.transcript ?? "";
      if (result.isFinal) finalText += text;
      else interim += text;
    }
    if (interim) handlers.onInterim?.(finalText + interim);
    if (finalText) handlers.onInterim?.(finalText);
  };
  recognition.onerror = (event) => {
    const messages: Record<string, string> = {
      "not-allowed": "Microphone access was blocked. Allow it in the browser and try again.",
      "no-speech": "Didn't catch anything — try again and speak a little louder.",
      network: "Speech recognition needs an internet connection in this browser.",
      "audio-capture": "No microphone found.",
    };
    handlers.onError(messages[event.error] ?? `Speech recognition error: ${event.error}`);
  };
  recognition.onend = () => {
    if (finalText.trim()) handlers.onFinal(finalText.trim());
    handlers.onEnd?.();
  };
  recognition.start();
  return { stop: () => recognition.stop() };
}
