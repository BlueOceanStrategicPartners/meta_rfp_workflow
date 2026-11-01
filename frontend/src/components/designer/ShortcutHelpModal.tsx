type Props = { open: boolean; onClose: () => void };

const SHORTCUTS = [
  ["Enter", "Send message"],
  ["Shift + Enter", "New line"],
  ["?", "Show this help"],
  ["@", "Mention asset from library"],
];

export default function ShortcutHelpModal({ open, onClose }: Props) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-label="Keyboard shortcuts"
    >
      <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-[#121828] p-6">
        <h3 className="text-lg font-semibold">Keyboard shortcuts</h3>
        <ul className="mt-4 space-y-2 text-sm">
          {SHORTCUTS.map(([key, desc]) => (
            <li key={key} className="flex justify-between gap-4">
              <kbd className="rounded bg-white/10 px-2 py-0.5 font-mono text-xs">{key}</kbd>
              <span className="text-white/60">{desc}</span>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-6 w-full rounded-lg bg-violet-600 py-2 text-sm focus-visible:ring-2 focus-visible:ring-violet-400"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </div>
  );
}
