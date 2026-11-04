import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import type { MicPhase } from "../../hooks/useBrowserVoiceTranscribe";
import { useAppShell } from "../../context/AppShellContext";
import ThinkingDotsLine from "../voice/ThinkingDotsLine";

const ORBIT_RINGS = [1, 2, 3, 4] as const;
const RING_BASE_PX = 216;
const RING_STEP_PX = 32;
const RING_COUNT = ORBIT_RINGS.length;

/** Smooth ease-in-out (no spring snap on mount) */
const EASE_IN_OUT: [number, number, number, number] = [0.45, 0.05, 0.25, 1];
const RING_INTRO_STAGGER_S = 0.12;
const RING_INTRO_DURATION_S = 0.62;

/** 0 = innermost ring, 1 = outermost — drives opacity + stroke segments */
function ringSegment(ring: number): number {
  return (ring - 1) / Math.max(1, RING_COUNT - 1);
}

/** Inner rings rest/peak high; outer rings stay low even at peak */
function ringOpacitySegment(ring: number, light: boolean): { rest: number; peak: number } {
  const t = ringSegment(ring);
  if (light) {
    return {
      rest: 0.58 - t * 0.34,
      peak: 0.86 - t * 0.48,
    };
  }
  return {
    rest: 0.54 - t * 0.46,
    peak: 0.8 - t * 0.64,
  };
}

/** Light mode: arc blue (inner) blended into slate–navy (outer). */
function lightRingStrokeRgb(ring: number): string {
  const t = ringSegment(ring);
  const r = Math.round(29 + t * 42);
  const g = Math.round(78 + t * 7);
  const b = Math.round(216 - t * 111);
  return `${r}, ${g}, ${b}`;
}

function ringStrokeColor(
  ring: number,
  opts: { debate: boolean; micLive: boolean; voiceMode: boolean; light: boolean },
): string {
  const t = ringSegment(ring);
  const innerAlpha = opts.light ? 0.55 : 0.48;
  const outerAlpha = opts.light ? 0.22 : 0.14;
  const alpha = innerAlpha - t * (innerAlpha - outerAlpha);

  if (opts.light) {
    const rgb = lightRingStrokeRgb(ring);
    if (opts.debate) return `rgba(180, 120, 6, ${alpha * 0.9})`;
    if (opts.micLive) return `rgba(4, 120, 87, ${alpha * 0.95})`;
    if (opts.voiceMode) return `rgba(${rgb}, ${alpha * 0.92})`;
    return `rgba(${rgb}, ${alpha})`;
  }

  if (opts.debate) return `rgba(251, 191, 36, ${alpha * 0.95})`;
  if (opts.micLive) return `rgba(52, 211, 153, ${alpha})`;
  if (opts.voiceMode) return `rgba(45, 212, 191, ${alpha * 0.85})`;
  return `rgba(34, 211, 238, ${alpha})`;
}

type Props = {
  levels: number[];
  debateRings?: number;
  agentSpeaking?: boolean;
  thinking?: boolean;
  voiceMode?: boolean;
  micPhase?: MicPhase;
  onVoiceToggle?: () => void;
};

export default function CentralVoiceOrb({
  levels,
  debateRings = 0,
  agentSpeaking = false,
  thinking = false,
  voiceMode = false,
  micPhase = "idle",
  onVoiceToggle,
}: Props) {
  const { theme } = useAppShell();
  const lightTheme = theme === "light";
  const [tick, setTick] = useState(0);
  const micLive = micPhase === "live";
  const micActive = micLive || agentSpeaking;
  /** From end of user turn until agent speaks (voice pause + backend work). */
  const showThinking =
    !agentSpeaking && (thinking || (voiceMode && micPhase === "paused"));

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
    if (showThinking) return { title: "Thinking", hint: null };
    if (agentSpeaking) return { title: "Speaking", hint: "Agent reply" };
    if (micPhase === "connecting") return { title: "Starting", hint: "Voice input…" };
    if (micPhase === "paused") return { title: "Voice on", hint: "Paused for reply" };
    if (micLive) return { title: "Voice on", hint: "Tap to exit" };
    return { title: "Voice", hint: "Tap to talk" };
  })();

  const ringAnimateOpacity = (ring: number): number | number[] => {
    const { rest, peak } = ringOpacitySegment(ring, lightTheme);
    const debate = debateRings >= ring;

    if (debate) {
      const t = ringSegment(ring);
      const lo = 0.28 - t * 0.14;
      const hi = 0.52 - t * 0.34;
      return [lo, hi, lo];
    }
    if (showThinking) {
      const t = ringSegment(ring);
      const r = rest * (0.65 - t * 0.12);
      const p = rest + (peak - rest) * (0.5 - t * 0.15);
      return [r, p, r];
    }
    if (micActive) {
      const r = rest + energy * 0.06;
      const p = rest + (peak - rest) * (0.55 + energy * 0.45);
      return [r, Math.min(peak, p), r];
    }
    if (voiceMode) return [rest * 0.72, rest * 1.08, rest * 0.72];
    return rest;
  };

  const ringOpacityTarget = (ring: number) => ringAnimateOpacity(ring);

  const ringTransition = (ring: number) => {
    const opacityTarget = ringOpacityTarget(ring);
    const pulse = Array.isArray(opacityTarget);
    const introDelay = 0.06 + ring * RING_INTRO_STAGGER_S;
    return {
      opacity: pulse
        ? {
            duration: 1.55 + ring * 0.22,
            repeat: Infinity,
            ease: EASE_IN_OUT,
            delay: RING_INTRO_DURATION_S + introDelay,
            repeatType: "mirror" as const,
          }
        : {
            duration: RING_INTRO_DURATION_S,
            ease: EASE_IN_OUT,
            delay: introDelay,
          },
      scale: micActive
        ? {
            duration: 1.05,
            repeat: Infinity,
            ease: EASE_IN_OUT,
            delay: RING_INTRO_DURATION_S + introDelay,
            repeatType: "mirror" as const,
          }
        : showThinking
          ? {
              duration: 2.4,
              repeat: Infinity,
              ease: EASE_IN_OUT,
              delay: RING_INTRO_DURATION_S + introDelay,
              repeatType: "mirror" as const,
            }
          : {
              duration: RING_INTRO_DURATION_S,
              ease: EASE_IN_OUT,
              delay: introDelay,
            },
      rotate: {
        duration: 6 + ring * 1.05,
        repeat: Infinity,
        ease: "linear",
        delay: RING_INTRO_DURATION_S + introDelay + 0.15,
      },
    };
  };

  return (
    <div className="relative flex flex-col items-center justify-center">
      <div className="relative flex items-center justify-center size-[22rem]">
        {ORBIT_RINGS.map((ring) => {
          const size = RING_BASE_PX + ring * RING_STEP_PX;
          const stroke = ringStrokeColor(ring, {
            debate: debateRings >= ring,
            micLive,
            voiceMode,
            light: lightTheme,
          });
          return (
            <motion.div
              key={ring}
              aria-hidden
              className="pointer-events-none absolute z-0 rounded-full border bg-transparent"
              style={{ width: size, height: size, borderColor: stroke }}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{
                opacity: ringOpacityTarget(ring),
                rotate:
                  debateRings >= ring || micActive
                    ? 360
                    : showThinking
                      ? 240
                      : voiceMode
                        ? 180
                        : 0,
                scale: micActive ? [1, 1 + energy * 0.022, 1] : showThinking ? [1, 1.012, 1] : 1,
              }}
              transition={ringTransition(ring)}
            />
          );
        })}

        <motion.button
          type="button"
          aria-pressed={voiceMode}
          aria-label={
            showThinking
              ? "Assistant is thinking"
              : voiceMode
                ? "Exit voice mode"
                : "Enter voice mode"
          }
          disabled={agentSpeaking}
          onClick={() => onVoiceToggle?.()}
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: showThinking ? [1, 1.015, 1] : 1 }}
          transition={
            showThinking
              ? { opacity: { duration: 0.55, ease: EASE_IN_OUT, delay: 0.04 }, scale: { duration: 2.2, repeat: Infinity, ease: EASE_IN_OUT, repeatType: "mirror" } }
              : { duration: 0.55, ease: EASE_IN_OUT, delay: 0.04 }
          }
          className={`relative z-10 w-52 h-52 rounded-full border bg-[#0f172a]/95 bg-gradient-to-b from-[#0c4a5e] via-[#172554] to-[#0f172a] cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70 disabled:cursor-not-allowed disabled:opacity-50 ${
            debateRings > 0
              ? "shadow-[0_0_70px_rgba(251,191,36,0.22)]"
              : "shadow-[0_0_60px_rgba(34,211,238,0.25)]"
          } ${
            showThinking
              ? "border-violet-300/50 shadow-[0_0_72px_rgba(167,139,250,0.28)]"
              : agentSpeaking
              ? "border-cyan-300/60"
              : micLive
                ? "border-emerald-300/70 shadow-[0_0_70px_rgba(52,211,153,0.35)]"
                : voiceMode
                  ? "border-teal-400/45"
                  : "border-cyan-500/40 hover:border-teal-300/55 hover:from-[#0e5668] hover:to-[#1e293b]"
          }`}
          whileTap={agentSpeaking ? undefined : { scale: 0.97 }}
        >
          <motion.span
            className="absolute inset-3 rounded-full border border-teal-400/35 pointer-events-none bg-transparent"
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{
              opacity: micActive ? [0.45, 0.85, 0.45] : voiceMode ? [0.3, 0.55, 0.3] : 0.35,
              scale: micActive ? [1, 1.04 + energy * 0.06, 1] : 1,
            }}
            transition={{
              opacity: micActive || voiceMode
                ? {
                    duration: 1.4,
                    repeat: Infinity,
                    ease: EASE_IN_OUT,
                    delay: 0.45,
                    repeatType: "mirror",
                  }
                : { duration: 0.5, ease: EASE_IN_OUT, delay: 0.35 },
              scale: micActive
                ? {
                    duration: 1.4,
                    repeat: Infinity,
                    ease: EASE_IN_OUT,
                    delay: 0.45,
                    repeatType: "mirror",
                  }
                : { duration: 0.5, ease: EASE_IN_OUT, delay: 0.35 },
            }}
          />
          <span className="relative z-10 flex flex-col items-center justify-center h-full px-6 text-center pointer-events-none">
            <span
              className={`text-[11px] uppercase tracking-[0.2em] ${
                showThinking
                  ? "text-violet-200"
                  : micLive || voiceMode
                    ? "text-emerald-200"
                    : "text-cyan-200/80"
              }`}
            >
              {statusLine.title}
            </span>
            {showThinking ? (
              <ThinkingDotsLine className="mt-4" colorClassName="text-cyan-50/95" aria-hidden />
            ) : (
              <span className="mt-2 text-xs text-cyan-100/45">{statusLine.hint}</span>
            )}
          </span>
        </motion.button>
      </div>
    </div>
  );
}
