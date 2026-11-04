import { motion } from "framer-motion";
import { IconComposerMic } from "./ClientComposerIcons";
import ComposerTooltip from "./ComposerTooltip";
import { IconMic } from "../designer/TemplateIconButton";

type Props = {
  listening: boolean;
  onToggle: () => void;
  variant?: "client" | "designer";
  disabled?: boolean;
};

const spring = { type: "spring" as const, stiffness: 520, damping: 28 };

/** Mic toggle with listening pulse — fills composer via useComposerSpeechDictation. */
export default function ComposerVoiceDictationButton({
  listening,
  onToggle,
  variant = "client",
  disabled = false,
}: Props) {
  const tooltip = listening ? "Listening — tap to stop" : "Voice input";

  const button =
    variant === "designer" ? (
      <motion.button
        type="button"
        disabled={disabled}
        aria-label={tooltip}
        aria-pressed={listening}
        title={tooltip}
        onClick={onToggle}
        className={[
          "studio-composer-action relative overflow-hidden",
          listening ? "studio-composer-action--listening" : "",
        ].join(" ")}
        whileHover={disabled ? undefined : { scale: 1.05 }}
        whileTap={disabled ? undefined : { scale: 0.95 }}
        transition={spring}
      >
        {listening ? (
          <motion.span
            className="studio-composer-action__pulse pointer-events-none absolute inset-0 rounded-lg"
            aria-hidden
            animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
          />
        ) : null}
        <motion.span
          className="relative flex items-center justify-center"
          animate={listening ? { scale: [1, 1.06, 1] } : { scale: 1 }}
          transition={listening ? { duration: 0.85, repeat: Infinity, ease: "easeInOut" } : spring}
        >
          <IconMic />
        </motion.span>
      </motion.button>
    ) : (
      <motion.button
        type="button"
        disabled={disabled}
        aria-label={tooltip}
        aria-pressed={listening}
        onClick={onToggle}
        className={[
          "client-composer-voice client-composer-icon-btn relative overflow-hidden",
          listening ? "client-composer-voice--active client-composer-voice--listening" : "",
        ].join(" ")}
        whileHover={disabled ? undefined : { scale: 1.06 }}
        whileTap={disabled ? undefined : { scale: 0.94 }}
        transition={spring}
      >
        {listening ? (
          <motion.span
            className="client-composer-voice__pulse pointer-events-none absolute inset-0 rounded-full"
            aria-hidden
            animate={{ scale: [1, 1.35, 1], opacity: [0.45, 0, 0.45] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
          />
        ) : null}
        <motion.span
          className="relative flex items-center justify-center"
          animate={listening ? { scale: [1, 1.05, 1] } : { scale: 1 }}
          transition={listening ? { duration: 0.85, repeat: Infinity, ease: "easeInOut" } : spring}
        >
          <IconComposerMic />
        </motion.span>
      </motion.button>
    );

  if (variant === "designer") return button;

  return <ComposerTooltip label={tooltip}>{button}</ComposerTooltip>;
}
