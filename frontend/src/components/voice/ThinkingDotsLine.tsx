import { motion } from "framer-motion";

const DOT_SIZES_PX = [6, 10, 14] as const;

type Props = {
  className?: string;
  /** Tailwind text color on wrapper (dots use `currentColor`). */
  colorClassName?: string;
  "aria-hidden"?: boolean;
};

/** Classic three-dot “working” indicator — ascending dot sizes, staggered bounce. */
export default function ThinkingDotsLine({
  className = "",
  colorClassName = "text-cyan-100",
  "aria-hidden": ariaHidden,
}: Props) {
  return (
    <span
      className={`inline-flex items-end justify-center gap-2 ${colorClassName} ${className}`.trim()}
      role={ariaHidden ? undefined : "status"}
      aria-label={ariaHidden ? undefined : "Thinking"}
      aria-hidden={ariaHidden}
    >
      {DOT_SIZES_PX.map((size, i) => (
        <motion.span
          key={size}
          className="block shrink-0 rounded-full bg-current"
          style={{ width: size, height: size }}
          animate={{ opacity: [0.28, 1, 0.28], scale: [0.88, 1.08, 0.88] }}
          transition={{
            duration: 0.95,
            repeat: Infinity,
            delay: i * 0.16,
            ease: "easeInOut",
          }}
        />
      ))}
    </span>
  );
}
