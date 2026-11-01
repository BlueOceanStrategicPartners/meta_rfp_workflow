type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: "default" | "danger";
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmVariant = "default",
  confirmDisabled = false,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;
  const confirmClass =
    confirmVariant === "danger"
      ? "rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 focus-visible:ring-2 focus-visible:ring-red-400"
      : "rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium hover:bg-violet-500 focus-visible:ring-2 focus-visible:ring-violet-400";
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#121828] p-6 shadow-2xl">
        <h3 id="confirm-title" className="text-lg font-semibold">
          {title}
        </h3>
        <p className="mt-2 text-sm text-white/65">{message}</p>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-white/15 px-4 py-2 text-sm hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirmDisabled}
            className={
              confirmClass + (confirmDisabled ? " cursor-not-allowed opacity-60" : "")
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
