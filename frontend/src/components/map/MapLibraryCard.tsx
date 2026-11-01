import { useMemo } from "react";
import { compileLocalMapPreview } from "../../lib/mapStudioPreview";
import type { VenueMapRecord } from "../../lib/mapStudioApi";

type Props = {
  map: VenueMapRecord;
  selected: boolean;
  onSelect: () => void;
};

export default function MapLibraryCard({ map, selected, onSelect }: Props) {
  const previewDoc = useMemo(
    () => compileLocalMapPreview(map.html_markup, map.css_stylesheet, map.js_script || ""),
    [map.html_markup, map.css_stylesheet, map.js_script]
  );

  const hasContent = Boolean((map.html_markup || "").trim());

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`studio-template-card w-full text-left transition ${selected ? "studio-template-card--active" : ""}`}
    >
      <div className="studio-template-card-preview" aria-hidden>
        {hasContent ? (
          <iframe
            title=""
            tabIndex={-1}
            className="studio-template-card-iframe"
            sandbox="allow-scripts allow-same-origin"
            loading="lazy"
            srcDoc={previewDoc}
          />
        ) : (
          <div className="studio-template-card-empty">
            <span className="text-2xl opacity-40">🗺</span>
            <span className="text-[10px] text-white/35">No map yet</span>
          </div>
        )}
      </div>
      <div className="studio-template-card-meta">
        <p className="truncate text-sm font-medium text-white/95">{map.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-white/40">
          <time dateTime={map.updated_at}>{new Date(map.updated_at).toLocaleString()}</time>
          {map.is_default && (
            <span className="rounded-full bg-amber-500/20 px-1.5 py-0.5 font-medium text-amber-200">
              Default
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
