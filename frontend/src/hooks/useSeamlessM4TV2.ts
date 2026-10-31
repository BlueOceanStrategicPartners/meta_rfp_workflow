import { useCallback, useEffect, useRef } from "react";

import {
  playWavBlob,
  primeAudioSync,
  resumeAudioContext,
  speakWithSpeechSynthesis,
  stopActivePlayback,
} from "../lib/audioEngine";

type SpeakOptions = {
  srcLang?: string;
  tgtLang?: string;
  onProgress?: (currentTime: number, duration: number) => void;
};

export type SpeakResult =
  | { ok: true; duration: number }
  | {
      ok: false;
      reason: "empty" | "aborted" | "http" | "play_blocked" | "error";
      detail?: string;
    };

export function useSeamlessM4TV2(onPlaybackStart?: () => void, onPlaybackEnd?: () => void) {
  const abortRef = useRef<AbortController | null>(null);
  const generationRef = useRef(0);
  const speakingRef = useRef(false);
  const onStartRef = useRef(onPlaybackStart);
  const onEndRef = useRef(onPlaybackEnd);
  onStartRef.current = onPlaybackStart;
  onEndRef.current = onPlaybackEnd;

  const endPlayback = useCallback(() => {
    if (!speakingRef.current) return;
    speakingRef.current = false;
    onEndRef.current?.();
  }, []);

  const interruptActiveSpeech = useCallback(() => {
    generationRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    stopActivePlayback();
    endPlayback();
  }, [endPlayback]);

  const stopSpeaking = interruptActiveSpeech;

  const speak = useCallback(
    async (text: string, options: SpeakOptions = {}): Promise<SpeakResult> => {
      const cleaned = text.trim();
      if (!cleaned) return { ok: false, reason: "empty" };

      interruptActiveSpeech();
      const generation = generationRef.current;
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch("/api/voice/seamless-m4t-v2/synthesize/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: cleaned.slice(0, 500),
            src_lang: options.srcLang,
            tgt_lang: options.tgtLang,
          }),
          signal: controller.signal,
        });

        if (generation !== generationRef.current) {
          return { ok: false, reason: "aborted" };
        }
        if (!res.ok) {
          return { ok: false, reason: "http", detail: String(res.status) };
        }

        const fixtureTone = res.headers.get("X-Voice-Fixture") === "1";

        speakingRef.current = true;
        onStartRef.current?.();

        const playResult = fixtureTone
          ? await speakWithSpeechSynthesis(cleaned, options.onProgress)
          : await playWavBlob(await res.blob(), options.onProgress);

        if (generation !== generationRef.current) {
          endPlayback();
          return { ok: false, reason: "aborted" };
        }

        if (!playResult.ok) {
          endPlayback();
          if (playResult.reason === "play_blocked") {
            return { ok: false, reason: "play_blocked" };
          }
          return { ok: false, reason: "error", detail: playResult.detail || playResult.reason };
        }

        endPlayback();
        return { ok: true, duration: playResult.duration };
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return { ok: false, reason: "aborted" };
        }
        endPlayback();
        return { ok: false, reason: "error", detail: (err as Error).message };
      }
    },
    [interruptActiveSpeech, endPlayback],
  );

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      stopActivePlayback();
      speakingRef.current = false;
    };
  }, []);

  return { speak, stopSpeaking, isSpeaking: () => speakingRef.current };
}

export async function unlockBrowserAudio(): Promise<boolean> {
  primeAudioSync();
  try {
    await resumeAudioContext();
    return true;
  } catch {
    return false;
  }
}

export { primeAudioSync };
