import { useEffect, useRef } from "react";
import ConfirmDialog from "../designer/ConfirmDialog";

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  busyLabel?: string;
  busy?: boolean;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/**
 * The shared ConfirmDialog, plus Esc to cancel and readable colours in both themes
 * (via `.admin-dialog-host` in admin.css). The designer component itself is not changed.
 */
export default function AdminConfirm({
  open,
  title,
  message,
  confirmLabel,
  busyLabel,
  busy = false,
  danger = false,
  onConfirm,
  onCancel,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null);

  // Move focus into the dialog (Cancel first, the safe choice).
  useEffect(() => {
    if (!open) return;
    const btn = hostRef.current?.querySelector<HTMLButtonElement>('[role="dialog"] button');
    btn?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;
  return (
    <div className="admin-dialog-host" ref={hostRef}>
      <ConfirmDialog
        open={open}
        title={title}
        message={message}
        confirmLabel={busy ? (busyLabel ?? "Working…") : confirmLabel}
        cancelLabel="Cancel"
        confirmVariant={danger ? "danger" : "default"}
        confirmDisabled={busy}
        onConfirm={() => {
          if (!busy) onConfirm();
        }}
        onCancel={() => {
          if (!busy) onCancel();
        }}
      />
    </div>
  );
}
