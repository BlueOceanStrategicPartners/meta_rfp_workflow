import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useId, useState, type ReactNode } from "react";

type Props = {
  label: string;
  children: ReactNode;
  /** Tooltip appears above the control (composer sits at bottom). */
  placement?: "top" | "bottom";
};

/** Hover/focus tooltip for composer icon buttons — theme-aware, animated. */
export default function ComposerTooltip({ label, children, placement = "top" }: Props) {
  const id = useId();
  const [visible, setVisible] = useState(false);

  const show = useCallback(() => setVisible(true), []);
  const hide = useCallback(() => setVisible(false), []);

  const positionClass =
    placement === "top"
      ? "bottom-[calc(100%+0.45rem)] origin-bottom"
      : "top-[calc(100%+0.45rem)] origin-top";

  return (
    <span
      className="client-composer-tooltip-host relative inline-flex max-w-full"
      onPointerEnter={show}
      onPointerLeave={hide}
      onFocusCapture={show}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) hide();
      }}
    >
      <span aria-describedby={visible ? id : undefined} className="inline-flex">
        {children}
      </span>
      <AnimatePresence>
        {visible ? (
          <motion.span
            id={id}
            role="tooltip"
            initial={{ opacity: 0, y: placement === "top" ? 8 : -8, scale: 0.92 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: placement === "top" ? 6 : -6, scale: 0.94 }}
            transition={{ type: "spring", stiffness: 480, damping: 32, mass: 0.65 }}
            className={[
              "client-composer-tooltip pointer-events-none absolute left-1/2 z-[70] -translate-x-1/2",
              placement === "top" ? "client-composer-tooltip--top" : "client-composer-tooltip--bottom",
              positionClass,
            ].join(" ")}
          >
            {label}
          </motion.span>
        ) : null}
      </AnimatePresence>
    </span>
  );
}
