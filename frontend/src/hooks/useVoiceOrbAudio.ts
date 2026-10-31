import { useCallback, useState } from "react";

/** Idle orb bar animation when mic is not active. */
export function useVoiceOrbAudio(active: boolean) {
  const [levels, setLevels] = useState<number[]>(() => Array(24).fill(0.1));

  const synthesizePulse = useCallback(() => {
    setLevels(Array.from({ length: 24 }, () => 0.2 + Math.random() * 0.7));
  }, []);

  const setExternalLevels = useCallback((next: number[]) => {
    if (active) setLevels(next.slice(0, 24));
  }, [active]);

  return { levels: active ? levels : Array(24).fill(0.12), synthesizePulse, setExternalLevels };
}
