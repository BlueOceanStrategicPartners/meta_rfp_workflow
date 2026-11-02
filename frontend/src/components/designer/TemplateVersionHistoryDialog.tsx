import type { TemplateRevision } from "../../lib/designerApi";

type Props = {
  open: boolean;
  templateName: string;
  revisions: TemplateRevision[];
  busy?: boolean;
  onClose: () => void;
  onRestore: (index: number) => void;
};

export default function TemplateVersionHistoryDialog({
  open,
  templateName,
  revisions,
  busy,
  onClose,
  onRestore,
}: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="template-history-title"
      onClick={onClose}
    >
      <div
        className="flex max-h-[min(70vh,28rem)] w-full max-w-sm flex-col rounded-2xl border border-white/10 bg-[#121828] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="border-b border-white/10 px-4 py-3">
          <h3 id="template-history-title" className="text-sm font-semibold text-white">
            Version history
          </h3>
          <p className="mt-0.5 truncate text-xs text-white/50">{templateName}</p>
        </header>
        <ul className="studio-scroll min-h-0 flex-1 overflow-y-auto p-2">
          {revisions.length === 0 ? (
            <li className="px-2 py-6 text-center text-xs text-white/45">No saved versions yet.</li>
          ) : (
            [...revisions].reverse().map((rev, revIdx) => {
              const index = revisions.length - 1 - revIdx;
              return (
                <li key={`${rev.saved_at}-${index}`}>
                  <button
                    type="button"
                    disabled={busy}
                    className="flex w-full flex-col gap-0.5 rounded-lg px-3 py-2.5 text-left transition hover:bg-violet-500/10 disabled:opacity-50"
                    onClick={() => onRestore(index)}
                  >
                    <span className="text-xs font-medium text-violet-100">
                      {new Date(rev.saved_at).toLocaleString()}
                    </span>
                    <span className="text-[11px] text-white/50">{rev.note || "Snapshot"}</span>
                    <span className="text-[10px] text-violet-300/80">Restore this version</span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
        <footer className="border-t border-white/10 px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg border border-white/15 py-2 text-sm text-white/80 hover:bg-white/5"
          >
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}
