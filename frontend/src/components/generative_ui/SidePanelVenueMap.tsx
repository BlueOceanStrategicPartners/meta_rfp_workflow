import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { downloadJson, type MapLocation } from "../../lib/mapStudioApi";

export type VenueMapSelection = {
  locationId: string;
  label: string;
  description: string;
  imageUrls: string[];
};

type Props = {
  open: boolean;
  onClose: () => void;
  /** Distance from viewport bottom (CSS length) — clears composer + map toggle */
  anchorBottom?: string;
  compiledHtml: string;
  highlights: string[];
  locations: MapLocation[];
  onSelectZone: (selection: VenueMapSelection) => void;
};

export function IconVenueMapPin({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      className="block"
      aria-hidden
    >
      <path d="M9 4l-5 2v14l5-2 6 2 5-2V4l-5 2-6-2z" />
      <path d="M9 4v14M15 6v14" />
      <circle cx="12" cy="10" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

export default function SidePanelVenueMap({
  open,
  onClose,
  anchorBottom = "11.25rem",
  compiledHtml,
  highlights,
  locations,
  onSelectZone,
}: Props) {
  const [detail, setDetail] = useState<VenueMapSelection | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data;
      if (!data || data.type !== "venue-map-select") return;
      const selection: VenueMapSelection = {
        locationId: String(data.locationId || ""),
        label: String(data.label || ""),
        description: String(data.description || ""),
        imageUrls: Array.isArray(data.imageUrls) ? data.imageUrls.map(String) : [],
      };
      setDetail(selection);
      onSelectZone(selection);
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onSelectZone]);

  useEffect(() => {
    if (!open) setDetail(null);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const downloadDetail = () => {
    if (!detail) return;
    const loc = locations.find(
      (l) => l.id === detail.locationId || (l as MapLocation & { location_id?: string }).location_id === detail.locationId,
    );
    downloadJson(`${detail.locationId || "location"}_details.json`, {
      ...detail,
      catalog: loc,
      exported_at: new Date().toISOString(),
    });
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button
            type="button"
            aria-label="Close venue map"
            className="fixed inset-0 z-30 cursor-default bg-[#070b14]/40 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-label="Venue map"
            className="fixed z-40 flex w-[min(420px,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-cyan-500/25 bg-[#0c121f]/95 shadow-[0_24px_80px_-20px_rgba(0,0,0,0.85),0_0_0_1px_rgba(34,211,238,0.08),inset_0_1px_0_rgba(34,211,238,0.12)] backdrop-blur-md"
            style={{
              right: "max(1rem, env(safe-area-inset-right, 0px))",
              bottom: `calc(${anchorBottom} + env(safe-area-inset-bottom, 0px))`,
            }}
            initial={{ opacity: 0, scale: 0.88, y: 20, filter: "blur(4px)" }}
            animate={{ opacity: 1, scale: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, scale: 0.92, y: 14, filter: "blur(2px)" }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 border-b border-cyan-500/15 px-3 py-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-200">
                <IconVenueMapPin size={16} />
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-sm font-semibold text-cyan-100">Venue map</h2>
                {highlights.length > 0 && (
                  <p className="truncate text-[10px] text-teal-300/80">Highlight: {highlights.join(", ")}</p>
                )}
              </div>
              {detail && (
                <button
                  type="button"
                  className="shrink-0 rounded-lg border border-teal-400/35 bg-teal-600/15 px-2 py-1 text-[10px] font-medium text-teal-100 hover:bg-teal-600/28"
                  onClick={downloadDetail}
                >
                  Export
                </button>
              )}
              <button
                type="button"
                aria-label="Close"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-cyan-400/20 text-cyan-200/80 transition hover:border-cyan-400/45 hover:bg-cyan-500/10 hover:text-cyan-100"
                onClick={onClose}
              >
                <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden>
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>

            <div className="relative aspect-[4/3] max-h-[min(52vh,360px)] min-h-[200px] w-full bg-[#070b14]">
              {compiledHtml ? (
                <iframe
                  ref={iframeRef}
                  title="Interactive venue map"
                  className="absolute inset-0 h-full w-full border-0 bg-white"
                  sandbox="allow-scripts allow-same-origin"
                  srcDoc={compiledHtml}
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
                  <span className="text-cyan-500/40">
                    <IconVenueMapPin size={32} />
                  </span>
                  <p className="text-sm text-cyan-100/45">No published venue map yet.</p>
                  <p className="text-[11px] text-teal-300/35">Publish a map from Map Studio to preview it here.</p>
                </div>
              )}
            </div>

            {detail && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                className="max-h-40 overflow-auto border-t border-cyan-500/15 px-3 py-2.5 text-sm"
              >
                <h3 className="text-sm font-semibold text-teal-200">{detail.label}</h3>
                <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-xs text-cyan-100/65">{detail.description}</p>
                {detail.imageUrls.length > 0 && (
                  <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
                    {detail.imageUrls.map((url) => (
                      <img
                        key={url}
                        src={url}
                        alt=""
                        className="h-16 w-24 shrink-0 rounded-lg border border-cyan-500/20 object-cover"
                      />
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
