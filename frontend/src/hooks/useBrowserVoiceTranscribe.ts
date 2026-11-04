import { useCallback, useEffect, useRef, useState } from "react";

import {
  getBrowserSpeechRecognitionCtor,
  type BrowserSpeechRecognition,
} from "../lib/browserSpeechRecognition";

/** Same debounce as server ASR hook — commit turn after a short pause. */
const TURN_COMMIT_DEBOUNCE_MS = 900;

export type MuseTranscribeState = "idle" | "connecting" | "listening" | "error";
export type MicPhase = "idle" | "connecting" | "live" | "paused" | "error";

type Options = {
  onFinalTranscript: (text: string) => void;
  onPartialTranscript?: (text: string) => void;
  onTurnPending?: (text: string) => void;
  onError?: (message: string) => void;
  onMicStopped?: () => void;
  onLevels?: (levels: number[]) => void;
};

/** Voice orb ASR via browser SpeechRecognition (no Whisper / backend WebSocket). */
export function useBrowserVoiceTranscribe(options: Options) {
  const [state, setState] = useState<MuseTranscribeState>("idle");
  const [micPhase, setMicPhase] = useState<MicPhase>("idle");
  const optsRef = useRef(options);
  optsRef.current = options;

  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const recognitionGenerationRef = useRef(0);
  const listeningRef = useRef(false);
  const pausedRef = useRef(false);
  const turnAccumRef = useRef("");
  const turnCommitTimerRef = useRef<number | null>(null);
  const levelsTimerRef = useRef<number | null>(null);
  const interimRef = useRef("");

  const clearTurnCommitTimer = useCallback(() => {
    if (turnCommitTimerRef.current != null) {
      window.clearTimeout(turnCommitTimerRef.current);
      turnCommitTimerRef.current = null;
    }
  }, []);

  const commitTurnToAssistant = useCallback(() => {
    clearTurnCommitTimer();
    const text = turnAccumRef.current.trim();
    turnAccumRef.current = "";
    interimRef.current = "";
    if (text) optsRef.current.onFinalTranscript(text);
  }, [clearTurnCommitTimer]);

  const queueTurnSegment = useCallback(
    (segment: string) => {
      const seg = segment.trim();
      if (!seg) return;
      turnAccumRef.current = turnAccumRef.current
        ? `${turnAccumRef.current} ${seg}`.trim()
        : seg;
      clearTurnCommitTimer();
      optsRef.current.onTurnPending?.(turnAccumRef.current);
      turnCommitTimerRef.current = window.setTimeout(
        commitTurnToAssistant,
        TURN_COMMIT_DEBOUNCE_MS,
      );
    },
    [clearTurnCommitTimer, commitTurnToAssistant],
  );

  const emitPartial = useCallback(() => {
    const base = turnAccumRef.current.trim();
    const interim = interimRef.current.trim();
    const combined = base && interim ? `${base} ${interim}` : base || interim;
    if (combined) optsRef.current.onPartialTranscript?.(combined);
  }, []);

  const stopLevelsAnimation = useCallback(() => {
    if (levelsTimerRef.current != null) {
      window.clearInterval(levelsTimerRef.current);
      levelsTimerRef.current = null;
    }
  }, []);

  const startLevelsAnimation = useCallback(() => {
    stopLevelsAnimation();
    let t = 0;
    levelsTimerRef.current = window.setInterval(() => {
      t += 0.15;
      optsRef.current.onLevels?.(
        Array.from({ length: 24 }, (_, i) =>
          Math.min(1, 0.18 + Math.abs(Math.sin(t + i * 0.45)) * 0.55),
        ),
      );
    }, 80);
  }, [stopLevelsAnimation]);

  const stopRecognition = useCallback(() => {
    const rec = recognitionRef.current;
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

  const attachRecognition = useCallback(() => {
    const Ctor = getBrowserSpeechRecognitionCtor();
    if (!Ctor) {
      optsRef.current.onError?.("Voice input is not supported in this browser. Try Chrome or Edge.");
      return false;
    }

    stopRecognition();
    const generation = ++recognitionGenerationRef.current;
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";

    rec.onstart = () => {
      if (recognitionGenerationRef.current !== generation) return;
      if (!listeningRef.current || pausedRef.current) return;
      setState("listening");
      setMicPhase("live");
      startLevelsAnimation();
    };

    rec.onresult = (ev) => {
      if (recognitionGenerationRef.current !== generation) return;
      if (!listeningRef.current || pausedRef.current) return;
      clearTurnCommitTimer();
      interimRef.current = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const chunk = ev.results[i][0]?.transcript || "";
        if (ev.results[i].isFinal) {
          queueTurnSegment(chunk);
        } else {
          interimRef.current += chunk;
        }
      }
      emitPartial();
    };

    rec.onerror = (ev) => {
      if (recognitionGenerationRef.current !== generation) return;
      if (ev.error === "aborted" || ev.error === "no-speech") return;
      if (ev.error === "not-allowed") {
        optsRef.current.onError?.("Microphone access was denied.");
      } else if (ev.error !== "network") {
        optsRef.current.onError?.("Voice input stopped. Tap the orb to try again.");
      }
      listeningRef.current = false;
      pausedRef.current = false;
      stopRecognition();
      stopLevelsAnimation();
      setState("error");
      setMicPhase("error");
      optsRef.current.onMicStopped?.();
    };

    rec.onend = () => {
      if (recognitionGenerationRef.current !== generation) return;
      if (!listeningRef.current || pausedRef.current) return;
      try {
        rec.start();
      } catch {
        if (recognitionGenerationRef.current !== generation) return;
        attachRecognition();
      }
    };

    recognitionRef.current = rec;
    try {
      rec.start();
      return true;
    } catch {
      optsRef.current.onError?.("Could not start voice listening.");
      return false;
    }
  }, [
    emitPartial,
    queueTurnSegment,
    clearTurnCommitTimer,
    startLevelsAnimation,
    stopRecognition,
  ]);

  const stopListening = useCallback(() => {
    recognitionGenerationRef.current += 1;
    listeningRef.current = false;
    pausedRef.current = false;
    clearTurnCommitTimer();
    turnAccumRef.current = "";
    interimRef.current = "";
    stopRecognition();
    stopLevelsAnimation();
    setState("idle");
    setMicPhase("idle");
  }, [clearTurnCommitTimer, stopLevelsAnimation, stopRecognition]);

  const pauseListening = useCallback(() => {
    recognitionGenerationRef.current += 1;
    pausedRef.current = true;
    clearTurnCommitTimer();
    interimRef.current = "";
    stopRecognition();
    stopLevelsAnimation();
    setState("listening");
    setMicPhase("paused");
  }, [clearTurnCommitTimer, stopLevelsAnimation, stopRecognition]);

  const startListening = useCallback(async () => {
    if (!getBrowserSpeechRecognitionCtor()) {
      optsRef.current.onError?.("Voice input is not supported in this browser. Try Chrome or Edge.");
      return;
    }
    listeningRef.current = true;
    pausedRef.current = false;
    turnAccumRef.current = "";
    interimRef.current = "";
    setState("connecting");
    setMicPhase("connecting");
    const ok = attachRecognition();
    if (!ok) {
      stopListening();
      optsRef.current.onMicStopped?.();
    }
  }, [attachRecognition, stopListening]);

  const resumeListening = useCallback(async () => {
    if (!listeningRef.current) {
      return startListening();
    }
    if (!pausedRef.current && recognitionRef.current) {
      return;
    }
    pausedRef.current = false;
    setState("connecting");
    setMicPhase("connecting");
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, 150);
    });
    if (!listeningRef.current || pausedRef.current) return;
    let ok = attachRecognition();
    if (!ok) {
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, 300);
      });
      if (!listeningRef.current || pausedRef.current) return;
      ok = attachRecognition();
    }
    if (!ok) {
      setState("listening");
      setMicPhase("paused");
      optsRef.current.onError?.("Could not restart the microphone. Tap the orb to turn voice off and on.");
    }
  }, [attachRecognition, startListening]);

  useEffect(() => () => stopListening(), [stopListening]);

  return {
    state,
    micPhase,
    startListening,
    pauseListening,
    resumeListening,
    stopListening,
    isListening: state === "listening",
    isMicLive: micPhase === "live",
  };
}
