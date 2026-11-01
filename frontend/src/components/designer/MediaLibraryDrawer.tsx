import type { DesignerMediaAsset } from "../../lib/designerApi";

type Props = {
  open: boolean;
  assets: DesignerMediaAsset[];
  onClose: () => void;
  onInsertMention: (asset: DesignerMediaAsset) => void;
  onAttach: (asset: DesignerMediaAsset) => void;
};

export default function MediaLibraryDrawer({
  open,
  assets,
  onClose,
  onInsertMention,
  onAttach,
}: Props) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] flex justify-end bg-black/50 backdrop-blur-sm">
      <div
        className="flex h-full w-full max-w-md flex-col border-l border-white/10 bg-[#0c1220] shadow-2xl"
        role="dialog"
        aria-label="Media library"
      >
        <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div>
            <h3 className="font-semibold">Media library</h3>
            <p className="text-xs text-white/50">{assets.length} assets</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 px-3 py-1 text-sm hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            Close
          </button>
        </header>
        <ul className="flex-1 overflow-y-auto p-4 space-y-3">
          {assets.length === 0 && (
            <li className="rounded-xl border border-dashed border-white/15 p-6 text-center text-sm text-white/45">
              Upload images or videos via drag-and-drop or Attach.
            </li>
          )}
          {assets.map((a) => (
            <li
              key={a.id}
              className="flex gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3"
            >
              {a.media_type === "VIDEO" ? (
                <video src={a.url} className="h-16 w-24 shrink-0 rounded-lg object-cover" muted />
              ) : (
                <img src={a.url} alt="" className="h-16 w-24 shrink-0 rounded-lg object-cover" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{a.original_name}</p>
                <p className="mt-1 line-clamp-2 text-xs text-white/45">
                  {String(a.metadata_json?.description || a.media_type)}
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  <button
                    type="button"
                    className="rounded-md bg-violet-600/80 px-2 py-0.5 text-[10px] hover:bg-violet-500 focus-visible:ring-2 focus-visible:ring-violet-400"
                    onClick={() => onAttach(a)}
                  >
                    Attach to send
                  </button>
                  <button
                    type="button"
                    className="rounded-md border border-white/15 px-2 py-0.5 text-[10px] hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-violet-500"
                    onClick={() => onInsertMention(a)}
                  >
                    @ Mention
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
