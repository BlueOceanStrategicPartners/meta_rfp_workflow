import { motion } from "framer-motion";

type Props = {
  agentSpeaking?: boolean;
  thinking?: boolean;
  voiceMode?: boolean;
  micLive?: boolean;
  onVoiceToggle?: () => void;
};

/** Compact orb for proposal view — sits inline with the composer. */
export default function ClientMiniVoiceOrb({
  agentSpeaking = false,
  thinking = false,
  voiceMode = false,
  micLive = false,
  onVoiceToggle,
}: Props) {
  const active = agentSpeaking || micLive || voiceMode || thinking;
  return (
    <motion.button
      type="button"
      aria-label={voiceMode ? "Voice mode on" : "Enter voice mode"}
      onClick={onVoiceToggle}
      className="client-composer-attach client-mini-orb flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[9px] font-semibold uppercase tracking-wide"
      animate={active ? { scale: [1, 1.06, 1] } : { scale: 1 }}
      transition={{ duration: 1.2, repeat: active ? Infinity : 0 }}
    >
      {agentSpeaking ? "Talk" : micLive ? "Mic" : thinking ? "…" : "Voice"}
    </motion.button>
  );
}
