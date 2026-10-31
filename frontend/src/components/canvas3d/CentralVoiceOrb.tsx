import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import type { MicPhase } from "../../hooks/useMuseVoiceTranscribe";

type Props = {
  levels: number[];
  debateRings?: number;
  agentSpeaking?: boolean;
  voiceMode?: boolean;
  micPhase?: MicPhase;
  onVoiceToggle?: () => void;
};

export default function CentralVoiceOrb({
  levels,
  debateRings = 0,
  agentSpeaking = false,
  voiceMode = false,
  micPhase = "idle",
  onVoiceToggle,
}: Props) {
  const [tick, setTick] = useState(0);
  const micLive = micPhase === "live";
  const micActive = micLive || agentSpeaking;

  useEffect(() => {
    if (!micActive) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 80);
    return () => window.clearInterval(id);
  }, [micActive]);

  const energy = useMemo(() => {
    const avg = levels.length ? levels.reduce((a, b) => a + b, 0) / levels.length : 0.12;
    if (!micActive) return avg * 0.35;
    return Math.min(1, 0.35 + avg * 0.45 + Math.sin(tick * 0.35) * 0.12);
  }, [levels, micActive, tick]);

  const statusLine = (() => {
    if (agentSpeaking) return { title: "Speaking", hint: "Agent reply" };
    if (micPhase === "connecting") return { title: "Loading", hint: "OmniASR worker…" };
    if (micPhase === "paused") return { title: "Voice on", hint: "Paused for reply" };
    if (micLive) return { title: "Voice on", hint: "Tap to exit" };
    return { title: "Voice", hint: "Tap to talk" };
  })();

  return (
    <div className="relative flex flex-col items-center justify-center w-72">
      <div className="relative flex items-center justify-center w-72 h-72">
        {[1, 2, 3].map((ring) => (
          <motion.div
            key={ring}
            className={`absolute rounded-full border ${
              micLive ? "border-emerald-400/40" : voiceMode ? "border-emerald-400/20" : "border-cyan-400/30"
            }`}
            style={{ width: 220 + ring * 34, height: 220 + ring * 34 }}
            animate={{
              opacity:
                debateRings >= ring
                  ? [0.35, 0.85, 0.35]
                  : micActive
                    ? [0.25 + energy * 0.2, 0.55 + energy * 0.35, 0.25 + energy * 0.2]
                    : voiceMode
                      ? [0.15, 0.35, 0.15]
                      : 0.12,
              rotate: debateRings >= ring || micActive ? 360 : voiceMode ? 180 : 0,
              scale: micActive ? [1, 1 + energy * 0.025, 1] : 1,
            }}
            transition={{
              rotate: { duration: 5 + ring * 1.2, repeat: Infinity, ease: "linear" },
              opacity: { duration: 1.6 + ring * 0.2, repeat: Infinity, ease: "easeInOut" },
              scale: { duration: 0.9, repeat: Infinity, ease: "easeInOut" },
            }}
          />
        ))}

        <motion.button
          type="button"
          aria-pressed={voiceMode}
          aria-label={voiceMode ? "Exit voice mode" : "Enter voice mode"}
          disabled={agentSpeaking}
          onClick={() => onVoiceToggle?.()}
          className={`relative w-52 h-52 rounded-full bg-gradient-to-b from-cyan-500/25 to-indigo-950/50 border shadow-[0_0_60px_rgba(34,211,238,0.25)] cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70 disabled:cursor-not-allowed disabled:opacity-50 ${
            agentSpeaking
              ? "border-cyan-300/60"
              : micLive
                ? "border-emerald-300/70 shadow-[0_0_70px_rgba(52,211,153,0.35)]"
                : voiceMode
                  ? "border-emerald-400/40"
                  : "border-white/25 hover:border-cyan-300/50 hover:bg-cyan-500/20"
          }`}
          whileTap={agentSpeaking ? undefined : { scale: 0.97 }}
        >
          <motion.span
            className="absolute inset-3 rounded-full border border-white/10"
            animate={{
              opacity: micActive ? [0.35, 0.7, 0.35] : voiceMode ? [0.25, 0.45, 0.25] : 0.2,
              scale: micActive ? [1, 1.04 + energy * 0.06, 1] : 1,
            }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
          />
          <span className="relative z-10 flex flex-col items-center justify-center h-full px-6 text-center pointer-events-none">
            <span
              className={`text-[11px] uppercase tracking-[0.2em] ${
                micLive || voiceMode ? "text-emerald-200" : "text-cyan-200/80"
              }`}
            >
              {statusLine.title}
            </span>
            <span className="mt-2 text-xs text-white/55">{statusLine.hint}</span>
          </span>
        </motion.button>
      </div>
    </div>
  );
}
