import { useMemo } from "react";
import { compileMapLibraryCardPreview, extractInteractiveMapMarkup } from "../../lib/mapLibraryPreview";
import type { VenueMapRecord } from "../../lib/mapStudioApi";
import TemplateIconButton, { IconStar, IconTrash } from "../designer/TemplateIconButton";

type Props = {
  map: VenueMapRecord;
  selected: boolean;
  onSelect: () => void;
  busy?: boolean;
  onSetDefault?: (id: string) => void;
  onDelete?: (id: string) => void;
};

export default function MapLibraryCard({
  map,
  selected,
  onSelect,
  busy,
  onSetDefault,
  onDelete,
}: Props) {
  const previewDoc = useMemo(
    () => compileMapLibraryCardPreview(map.html_markup, map.css_stylesheet, map.js_script || ""),
    [map.html_markup, map.css_stylesheet, map.js_script],
  );

  const mapFragment = Boolean(extractInteractiveMapMarkup(map.html_markup || ""));
  const showActions = Boolean(onSetDefault || onDelete);

  return (
    <div
      className={`studio-template-card w-full transition ${selected ? "studio-template-card--active" : ""}`}
    >
      <button type="button" onClick={onSelect} className="block w-full text-left">
        <div className="studio-template-card-preview" aria-hidden>
          {mapFragment ? (
            <div className="studio-template-card-preview-inset">
              <iframe
                title=""
                tabIndex={-1}
                className="studio-template-card-iframe"
                sandbox="allow-scripts allow-same-origin"
                loading="lazy"
                srcDoc={previewDoc}
              />
            </div>
          ) : (
            <div className="studio-template-card-empty m-2 rounded-lg">
              <span className="text-2xl opacity-40">🗺</span>
              <span className="text-[10px] text-white/35">No map yet</span>
            </div>
          )}
        </div>
      </button>
      <div className="studio-template-card-meta flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white/95">{map.title}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-white/40 tabular-nums">
            <time dateTime={map.updated_at}>{new Date(map.updated_at).toLocaleString()}</time>
            {map.is_default && <span className="text-violet-200/85">Default</span>}
          </div>
        </div>
        {showActions && (
          <div className="studio-template-actions shrink-0">
            {onSetDefault && (
              <TemplateIconButton
                compact
                label={map.is_default ? "Default venue map" : "Set as default venue map"}
                variant="accent"
                selected={map.is_default}
                disabled={busy || map.is_default}
                onClick={() => onSetDefault(map.id)}
              >
                <IconStar filled={map.is_default} />
              </TemplateIconButton>
            )}
            {onDelete && (
              <TemplateIconButton
                compact
                label="Delete venue map"
                variant="danger"
                disabled={busy}
                onClick={() => onDelete(map.id)}
              >
                <IconTrash />
              </TemplateIconButton>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
