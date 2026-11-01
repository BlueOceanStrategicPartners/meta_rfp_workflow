import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { useAppShell } from "../../context/AppShellContext";

export type SnackbarTone = "success" | "warning" | "error" | "info";

type StudioSnackbarProps = {
  open: boolean;
  message: string;
  tone?: SnackbarTone;
  onClose: () => void;
  durationMs?: number;
};

export function inferSnackbarTone(message: string): SnackbarTone {
  const lower = message.toLowerCase();
  if (lower.startsWith("valid")) return "success";
  if (lower.startsWith("issues") || lower.includes("missing")) return "warning";
  if (lower.includes("fail") || lower.includes("error")) return "error";
  return "info";
}

function toneClasses(tone: SnackbarTone, theme: "dark" | "light"): string {
  if (theme === "light") {
    const light: Record<SnackbarTone, string> = {
      success: "border-emerald-600 bg-emerald-50 text-emerald-950",
      warning: "border-amber-600 bg-amber-50 text-amber-950",
      error: "border-red-600 bg-red-50 text-red-950",
      info: "border-slate-400 bg-white text-slate-900",
    };
    return light[tone];
  }
  const dark: Record<SnackbarTone, string> = {
    success: "border-emerald-500/70 bg-[#0c2a1f] text-emerald-50",
    warning: "border-amber-500/70 bg-[#2a2010] text-amber-50",
    error: "border-red-500/70 bg-[#2a1212] text-red-50",
    info: "border-violet-400/40 bg-[#12182a] text-white",
  };
  return dark[tone];
}

export default function StudioSnackbar({
  open,
  message,
  tone = "info",
  onClose,
  durationMs = 5500,
}: StudioSnackbarProps) {
  const { theme } = useAppShell();

  const surface = useMemo(() => toneClasses(tone, theme), [tone, theme]);

  const closeBtnClass =
    theme === "light"
      ? "text-slate-500 hover:bg-slate-200/80 hover:text-slate-900"
      : "text-white/70 hover:bg-white/15 hover:text-white";

  useEffect(() => {
    if (!open || !message) return;
    const id = window.setTimeout(onClose, durationMs);
    return () => window.clearTimeout(id);
  }, [open, message, durationMs, onClose]);

  const content = (
    <AnimatePresence>
      {open && message ? (
        <motion.div
          role="status"
          aria-live="polite"
          className="pointer-events-none fixed inset-x-0 z-[200] flex justify-center px-4"
          style={{ top: "calc(var(--app-nav-height) + 0.75rem)" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            initial={{ opacity: 0, y: -24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ type: "spring", stiffness: 380, damping: 28 }}
            className="flex w-full max-w-xl justify-center"
          >
            <motion.div
              animate={{ y: [0, -5, 0] }}
              transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut", repeatDelay: 0.5 }}
              className={`pointer-events-auto relative w-full rounded-xl border-2 px-4 py-3.5 pr-10 shadow-[0_12px_40px_-8px_rgba(0,0,0,0.55)] ${surface}`}
            >
            <div className="flex items-start gap-2.5">
              <span
                className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  theme === "light" ? "bg-black/8" : "bg-black/25"
                }`}
                aria-hidden
              >
                {tone === "success" ? "✓" : tone === "warning" ? "!" : tone === "error" ? "✕" : "i"}
              </span>
              <p className="min-w-0 flex-1 text-sm font-medium leading-snug">{message}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className={`absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full text-sm leading-none transition ${closeBtnClass}`}
              aria-label="Close notification"
            >
              ×
            </button>
            </motion.div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === "undefined") return null;
  return createPortal(content, document.body);
}
