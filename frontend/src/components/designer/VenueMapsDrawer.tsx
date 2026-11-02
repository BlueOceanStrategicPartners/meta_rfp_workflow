import MapLibraryCard from "../map/MapLibraryCard";
import TemplateIconButton, { IconClose, IconUnlinkMap } from "./TemplateIconButton";
import type { MapRevision, VenueMapRecord } from "../../lib/mapStudioApi";

type Props = {
  open: boolean;
  maps: VenueMapRecord[];
  selectedId: string | null;
  busy: boolean;
  onClose: () => void;
  onSelect: (map: VenueMapRecord) => void;
  onSetDefault: (id: string) => void;
  onDelete: (id: string) => void;
  onRestoreRevision: (mapId: string, index: number) => void;
  onRemoveFromProposal: () => void;
  proposalHasMapSlot: boolean;
};

export default function VenueMapsDrawer({
  open,
  maps,
  selectedId,
  busy,
  onClose,
  onSelect,
  onSetDefault,
  onDelete,
  onRestoreRevision,
  onRemoveFromProposal,
  proposalHasMapSlot,
}: Props) {
  const selected = maps.find((m) => m.id === selectedId) ?? null;
  const revisions: MapRevision[] = selected?.revision_history_json ?? [];

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[95] flex justify-end bg-black/55"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="flex h-dvh w-full max-w-md flex-col border-l border-white/10 bg-[#0a0f1a] shadow-2xl"
        role="dialog"
        aria-label="Venue maps"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="studio-panel-header !min-h-[4rem]">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-widest text-white/45">Library</p>
            <h3 className="text-balance font-semibold text-white/95">Venue maps</h3>
            <p className="text-pretty text-[11px] text-white/45">
              {maps.length} saved · default drives Live preview
            </p>
          </div>
          <TemplateIconButton compact label="Close venue maps panel" onClick={onClose}>
            <IconClose />
          </TemplateIconButton>
        </header>

        <ul className="studio-scroll studio-panel-body min-h-0 flex-1 space-y-2.5 overflow-y-auto !py-4">
          {maps.length === 0 && (
            <li className="rounded-xl border border-dashed border-white/15 px-4 py-8 text-center text-sm text-white/45">
              No saved maps yet. Ask the design agent or attach a floorplan.
            </li>
          )}
          {maps.map((m) => (
            <li key={m.id} className="space-y-2">
              <MapLibraryCard
                map={m}
                selected={selectedId === m.id}
                busy={busy}
                onSelect={() => onSelect(m)}
                onSetDefault={onSetDefault}
                onDelete={onDelete}
              />
              {selectedId === m.id && revisions.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
                  <p className="text-[10px] font-medium uppercase text-white/40">Version history</p>
                  <ul className="studio-scroll mt-1.5 max-h-24 space-y-0.5 overflow-y-auto">
                    {revisions.map((rev, idx) => (
                      <li key={rev.saved_at + idx}>
                        <button
                          type="button"
                          disabled={busy}
                          className="w-full truncate rounded-md px-1 py-1 text-left text-[10px] text-violet-200/90 hover:bg-violet-500/10 disabled:opacity-40"
                          onClick={() => onRestoreRevision(m.id, idx)}
                        >
                          <span className="tabular-nums">{new Date(rev.saved_at).toLocaleString()}</span>
                          <span className="text-white/35"> · </span>
                          {rev.note}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ul>

        <footer className="studio-panel-footer !pb-5">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase text-white/40">This proposal</p>
              <p className="text-pretty text-[11px] text-white/45">
                Remove slot only — library maps stay saved
              </p>
            </div>
            <TemplateIconButton
              compact
              label="Remove map section from proposal"
              variant="danger"
              disabled={busy || !proposalHasMapSlot}
              onClick={onRemoveFromProposal}
            >
              <IconUnlinkMap />
            </TemplateIconButton>
          </div>
        </footer>
      </div>
    </div>
  );
}
