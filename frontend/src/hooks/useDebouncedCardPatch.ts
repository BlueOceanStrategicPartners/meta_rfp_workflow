import { useCallback, useEffect, useRef, useState } from "react";

export type CardSaveState = "idle" | "saving" | "saved" | "error";

/** Debounced merge-patch submit for RFP side cards (WebSocket mutation). */
export function useDebouncedCardPatch(
  submit: (patch: Record<string, unknown>) => void,
  delayMs = 550,
) {
  const timerRef = useRef<number | null>(null);
  const lastSentRef = useRef<string>("");

  const flush = useCallback(
    (patch: Record<string, unknown>) => {
      const key = JSON.stringify(patch);
      if (!key || key === "{}" || key === lastSentRef.current) return;
      lastSentRef.current = key;
      submit(patch);
    },
    [submit],
  );

  const queuePatch = useCallback(
    (patch: Record<string, unknown>) => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => flush(patch), delayMs);
    },
    [delayMs, flush],
  );

  useEffect(
    () => () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const resetSentFingerprint = useCallback(() => {
    lastSentRef.current = "";
  }, []);

  return { queuePatch, flushNow: flush, resetSentFingerprint };
}

export function useCardSaveState() {
  const [saveState, setSaveState] = useState<CardSaveState>("idle");
  const savedTimerRef = useRef<number | null>(null);

  const markSaving = useCallback(() => setSaveState("saving"), []);
  const markSaved = useCallback(() => {
    setSaveState("saved");
    if (savedTimerRef.current) window.clearTimeout(savedTimerRef.current);
    savedTimerRef.current = window.setTimeout(() => setSaveState("idle"), 2200);
  }, []);
  const markError = useCallback(() => setSaveState("error"), []);

  useEffect(
    () => () => {
      if (savedTimerRef.current) window.clearTimeout(savedTimerRef.current);
    },
    [],
  );

  return { saveState, markSaving, markSaved, markError };
}
