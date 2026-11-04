import { motion } from "framer-motion";
import { IconComposerMic } from "./ClientComposerIcons";
import ComposerTooltip from "./ComposerTooltip";

type Props = {
  agentSpeaking?: boolean;
  thinking?: boolean;
  voiceMode?: boolean;
  micLive?: boolean;
  onVoiceToggle?: () => void;
};

const spring = { type: "spring" as const, stiffness: 520, damping: 28 };

/** Compact voice control for proposal composer — icon + active animations. */
export default function ClientMiniVoiceOrb({
  agentSpeaking = false,
  thinking = false,
  voiceMode = false,
  micLive = false,
  onVoiceToggle,
}: Props) {
  const listening = micLive;
  const active = agentSpeaking || micLive || voiceMode || thinking;

  let ariaLabel = "Enter voice mode";
  if (agentSpeaking) ariaLabel = "Assistant speaking";
  else if (listening) ariaLabel = "Listening — tap to exit voice mode";
  else if (thinking) ariaLabel = "Assistant thinking";
  else if (voiceMode) ariaLabel = "Voice mode on — tap to toggle";

  const tooltip =
    agentSpeaking
      ? "Assistant speaking"
      : listening
        ? "Listening — tap to exit"
        : thinking
          ? "Thinking…"
          : voiceMode
            ? "Voice on — tap to turn off"
            : "Voice mode";

  return (
    <ComposerTooltip label={tooltip}>
      <motion.button
      type="button"
      aria-label={ariaLabel}
      aria-pressed={voiceMode || micLive}
      onClick={onVoiceToggle}
      className={[
        "client-composer-voice client-composer-icon-btn relative overflow-hidden",
        active ? "client-composer-voice--active" : "",
        listening ? "client-composer-voice--listening" : "",
        agentSpeaking ? "client-composer-voice--speaking" : "",
      ].join(" ")}
      whileHover={{ scale: 1.06 }}
      whileTap={{ scale: 0.94 }}
      transition={spring}
    >
      {active ? (
        <motion.span
          className="client-composer-voice__pulse pointer-events-none absolute inset-0 rounded-full"
          aria-hidden
          animate={{ scale: [1, 1.35, 1], opacity: [0.45, 0, 0.45] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        />
      ) : null}
      <motion.span
        className="relative flex items-center justify-center"
        animate={
          agentSpeaking
            ? { scale: [1, 1.08, 1], rotate: [0, -4, 4, 0] }
            : listening
              ? { scale: [1, 1.05, 1] }
              : thinking
                ? { opacity: [0.55, 1, 0.55] }
                : { scale: 1 }
        }
        transition={
          agentSpeaking || listening
            ? { duration: 0.85, repeat: Infinity, ease: "easeInOut" }
            : thinking
              ? { duration: 1.1, repeat: Infinity }
              : spring
        }
      >
        {thinking ? (
          <span className="flex gap-0.5" aria-hidden>
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="block h-1 w-1 rounded-full bg-current"
                animate={{ opacity: [0.35, 1, 0.35], y: [0, -2, 0] }}
                transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.12 }}
              />
            ))}
          </span>
        ) : (
          <IconComposerMic />
        )}
      </motion.span>
    </motion.button>
    </ComposerTooltip>
  );
}
