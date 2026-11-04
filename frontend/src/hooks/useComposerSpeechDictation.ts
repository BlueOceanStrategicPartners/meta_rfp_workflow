import { useCallback, useEffect, useRef, useState } from "react";

import { getBrowserSpeechRecognitionCtor, type BrowserSpeechRecognition } from "../lib/browserSpeechRecognition";

type Options = {
  getText: () => string;
  setText: (text: string) => void;
  onError?: (message: string) => void;
  lang?: string;
};

/** Browser continuous speech-to-text for composer fields (toggle on/off). */
export function useComposerSpeechDictation({ getText, setText, onError, lang = "en-US" }: Options) {
  const [listening, setListening] = useState(false);
  const listeningRef = useRef(false);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const sessionBaseRef = useRef("");
  const sessionFinalRef = useRef("");
  const optsRef = useRef({ getText, setText, onError, lang });
  optsRef.current = { getText, setText, onError, lang };

  const stop = useCallback(() => {
    listeningRef.current = false;
    setListening(false);
    const rec = recognitionRef.current as { stop: () => void; abort: () => void } | null;
    recognitionRef.current = null;
    try {
      rec?.stop();
    } catch {
      try {
        rec?.abort();
      } catch {
        /* ignore */
      }
    }
  }, []);

  const start = useCallback(() => {
    const Ctor = getBrowserSpeechRecognitionCtor();
    if (!Ctor) {
      optsRef.current.onError?.("Voice input is not supported in this browser.");
      return;
    }

    const existing = getText().trimEnd();
    sessionBaseRef.current = existing ? `${existing} ` : "";
    sessionFinalRef.current = "";

    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = optsRef.current.lang;

    rec.onresult = (ev) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const chunk = ev.results[i][0]?.transcript || "";
        if (ev.results[i].isFinal) {
          sessionFinalRef.current += chunk;
        } else {
          interim += chunk;
        }
      }
      optsRef.current.setText(sessionBaseRef.current + sessionFinalRef.current + interim);
    };

    rec.onerror = (ev) => {
      if (ev.error === "aborted" || ev.error === "no-speech") return;
      if (ev.error === "not-allowed") {
        optsRef.current.onError?.("Microphone access was denied.");
      } else if (ev.error !== "network") {
        optsRef.current.onError?.("Voice input stopped. Try again.");
      }
      stop();
    };

    rec.onend = () => {
      if (!listeningRef.current) return;
      try {
        rec.start();
      } catch {
        stop();
      }
    };

    recognitionRef.current = rec;
    listeningRef.current = true;
    setListening(true);
    try {
      rec.start();
    } catch {
      stop();
      optsRef.current.onError?.("Could not start voice input.");
    }
  }, [getText, stop]);

  const toggle = useCallback(() => {
    if (listeningRef.current) stop();
    else start();
  }, [start, stop]);

  useEffect(() => () => stop(), [stop]);

  return { listening, toggle, stop, start };
}
