import { AnimatePresence, motion } from "framer-motion";
import ThinkingDotsLine from "./ThinkingDotsLine";

export type CaptionLine = {
  id: string;
  role: "user" | "agent";
  text: string;
  /** 0–1 reveal progress while agent speaks */
  reveal: number;
  status: "done" | "speaking" | "pending";
};

type Props = {
  lines: CaptionLine[];
  agentSpeaking: boolean;
  thinking?: boolean;
  /** Shown while thinking when no agent caption yet (or as subtitle under dots). */
  progressText?: string | null;
};

function visibleText(full: string, reveal: number) {
  if (reveal >= 1) return full;
  const words = full.split(/(\s+)/);
  let chars = 0;
  const target = Math.floor(full.length * reveal);
  let out = "";
  for (const w of words) {
    if (chars + w.length > target) break;
    out += w;
    chars += w.length;
  }
  return out;
}

export default function VoiceAgentSubtitles({ lines, agentSpeaking, thinking, progressText }: Props) {
  const agentLine = [...lines].reverse().find((l) => l.role === "agent");
  const userLine = [...lines].reverse().find((l) => l.role === "user");

  return (
    <div className="w-full max-w-xl px-4 min-h-[4rem] flex flex-col items-center justify-end gap-2">
      <AnimatePresence mode="popLayout">
        {userLine && (
          <motion.p
            key={userLine.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="voice-caption-user text-center text-xs"
          >
            <span className="voice-caption-user-label mr-2">You</span>
            {userLine.text}
          </motion.p>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {thinking && !agentLine && (
          <motion.div
            key="thinking"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center gap-2 max-w-md"
          >
            <div className="voice-caption-thinking flex items-center gap-2 text-xs">
              <ThinkingDotsLine colorClassName="text-cyan-400" />
              {progressText || "Working on your request…"}
            </div>
          </motion.div>
        )}

        {agentLine && (
          <motion.div
            key={agentLine.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className={`voice-caption-agent relative w-full rounded-2xl border px-4 py-3 text-center ${
              agentSpeaking || agentLine.status === "speaking" ? "voice-caption-agent--live" : ""
            }`}
          >
            {(agentSpeaking || agentLine.status === "speaking") && (
              <motion.div
                className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-cyan-400/20"
                animate={{ opacity: [0.35, 0.65, 0.35] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
              />
            )}
            <p className="voice-caption-agent-label mb-1 text-[10px] uppercase tracking-widest">
              Assistant
            </p>
            <p className="voice-caption-agent-body text-sm leading-relaxed">
              {visibleText(agentLine.text, agentLine.reveal)}
              {(thinking ||
                agentSpeaking ||
                agentLine.status === "speaking") &&
                agentLine.reveal < 1 && (
                <motion.span
                  className="inline-block w-0.5 h-4 ml-0.5 align-middle bg-cyan-300"
                  animate={{ opacity: [1, 0, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                />
              )}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
