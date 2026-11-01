import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { IconVenueMapPin } from "./SidePanelVenueMap";

type Props = {
  open: boolean;
  onToggle: () => void;
};

const ICON_SIZE = 18;
const REST_SIZE = 40;
const HOVER_SIZE = REST_SIZE + 10;
const EXPANDED_WIDTH = 176;

const expandTransition = {
  duration: 0.42,
  ease: [0.45, 0.05, 0.25, 1] as const,
};

export default function VenueMapToggleButton({ open, onToggle }: Props) {
  const [hover, setHover] = useState(false);
  const expanded = hover || open;
  const label = open ? "Close venue map" : "Open venue map";

  return (
    <motion.button
      type="button"
      aria-label={label}
      aria-expanded={open}
      initial={false}
      onClick={onToggle}
      onHoverStart={() => setHover(true)}
      onHoverEnd={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      animate={{
        width: expanded ? EXPANDED_WIDTH : REST_SIZE,
        height: expanded ? HOVER_SIZE : REST_SIZE,
        paddingLeft: expanded ? 14 : 0,
        paddingRight: expanded ? 14 : 0,
      }}
      transition={expandTransition}
      className={`mt-5 relative flex shrink-0 items-center overflow-hidden rounded-full border shadow-[0_8px_32px_-12px_rgba(0,0,0,0.65)] backdrop-blur-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 ${
        expanded ? "justify-start gap-2" : "justify-center gap-0"
      } ${
        open
          ? "border-violet-400/55 bg-violet-600/25 text-violet-100"
          : "border-cyan-500/35 bg-[#0c121f]/75 text-cyan-200 hover:border-teal-400/50 hover:bg-cyan-950/50"
      }`}
    >
      <span className="inline-flex size-[18px] shrink-0 items-center justify-center leading-none">
        <IconVenueMapPin size={ICON_SIZE} />
      </span>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.span
            key="label"
            initial={{ opacity: 0, maxWidth: 0 }}
            animate={{ opacity: 1, maxWidth: 132 }}
            exit={{ opacity: 0, maxWidth: 0 }}
            transition={expandTransition}
            className="min-w-0 overflow-hidden whitespace-nowrap text-xs font-medium leading-none tracking-wide text-cyan-100/95 pointer-events-none select-none"
          >
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
