import { motion } from "framer-motion";
import type { ReactNode } from "react";

const ICON_SIZE = 14;
const ICON_STROKE = 1.75;

type Variant = "default" | "primary" | "danger" | "accent";

const variantClass: Record<Variant, string> = {
  default: "border-white/15 bg-white/[0.04] text-white/85 hover:border-white/25 hover:bg-white/[0.1]",
  primary: "border-emerald-500/50 bg-emerald-600/90 text-white hover:border-emerald-400 hover:bg-emerald-500",
  danger: "border-red-500/45 bg-red-950/50 text-red-100 hover:border-red-400/60 hover:bg-red-900/55",
  accent: "border-amber-500/45 bg-amber-950/40 text-amber-100 hover:border-amber-400/55 hover:bg-amber-900/45",
};

const selectedClass =
  "!border-violet-400/70 !bg-violet-600 !text-white shadow-[0_0_14px_-3px_rgba(139,92,246,0.75)]";

type TemplateIconButtonProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: Variant;
  active?: boolean;
  selected?: boolean;
  compact?: boolean;
  children: ReactNode;
};

export default function TemplateIconButton({
  label,
  onClick,
  disabled,
  variant = "default",
  active,
  selected,
  compact,
  children,
}: TemplateIconButtonProps) {
  return (
    <motion.button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={selected}
      disabled={disabled}
      onClick={onClick}
      whileHover={disabled ? undefined : { scale: 1.08, y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.92 }}
      transition={{ type: "spring", stiffness: 520, damping: 28 }}
      className={`studio-icon-btn ${compact ? "h-9 w-9 shrink-0 !flex-none" : ""} ${selected ? selectedClass : variantClass[variant]} ${active ? "ring-2 ring-amber-400/50" : ""} disabled:cursor-not-allowed disabled:opacity-40`}
    >
      {children}
    </motion.button>
  );
}

export function IconDuplicate() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

export function IconTrash() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
    </svg>
  );
}

export function IconSave() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <path d="M17 21v-8H7v8M7 3v5h8" />
    </svg>
  );
}

export function IconStar({ filled }: { filled?: boolean }) {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14l-5-4.87 6.91-1.01L12 2z" />
    </svg>
  );
}

export function IconExport() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M12 3v12M7 8l5-5 5 5M5 21h14" />
    </svg>
  );
}

export function IconHelp() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9a2.5 2.5 0 1 1 4.2 1.8c-.8.6-1.2 1.2-1.2 2.2M12 17h.01" />
    </svg>
  );
}

export function IconMediaLibrary() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="8.5" cy="10.5" r="1.5" />
      <path d="M21 16l-5-5-4 4-2-2-5 5" />
    </svg>
  );
}

export function IconRegenerate() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  );
}

export function IconUndo() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M9 14 4 9l5-5" />
      <path d="M20 20a8 8 0 0 0-14-4" />
    </svg>
  );
}

export function IconClearChat() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M4 7h16M9 7V5h6v2M10 11v6M14 11v6M6 7l1 12h10l1-12" />
    </svg>
  );
}

export function IconMonitor() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <rect x="2" y="4" width="20" height="13" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  );
}

export function IconTabletDevice() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M12 18h.01" />
    </svg>
  );
}

export function IconPhoneDevice() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <rect x="7" y="2" width="10" height="20" rx="2" />
      <path d="M12 18h.01" />
    </svg>
  );
}

export function IconExternalTab() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M14 3h7v7M10 14 21 3M21 14v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6" />
    </svg>
  );
}

export function IconFullscreen({ exit }: { exit?: boolean }) {
  if (exit) {
    return (
      <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
        <path d="M9 9 4 4M4 9V4h5M15 9l5-5M20 9V4h-5M9 15l-5 5M4 15v5h5M15 15l5 5M20 15v5h-5" />
      </svg>
    );
  }
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
    </svg>
  );
}

export function IconSampleData() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 4v16M16 4v16" />
    </svg>
  );
}

export function IconCheckTemplate() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M9 12l2 2 4-4" />
      <circle cx="12" cy="12" r="9" />
    </svg>
  );
}

export function IconSun() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

export function IconMoon() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3 7 7 0 0 0 21 14.5z" />
    </svg>
  );
}

export function IconLogout() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}

export function IconPaperclip() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M21.44 11.05l-8.49 8.49a5 5 0 0 1-7.07-7.07l9.19-9.19a3 3 0 0 1 4.24 4.24l-9.2 9.19a1 1 0 0 1-1.41-1.41l8.49-8.48" />
    </svg>
  );
}

export function IconMic() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z" />
      <path d="M19 11a7 7 0 0 1-14 0M12 18v3" />
    </svg>
  );
}

export function IconSendArrow() {
  return (
    <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={ICON_STROKE} aria-hidden>
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  );
}
