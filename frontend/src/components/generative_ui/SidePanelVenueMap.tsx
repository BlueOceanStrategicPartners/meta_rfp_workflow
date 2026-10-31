import { motion } from "framer-motion";

type Props = {
  open: boolean;
  svgMarkup: string;
  highlights: string[];
  onSelectZone: (zoneId: string) => void;
};

export default function SidePanelVenueMap({ open, svgMarkup, highlights, onSelectZone }: Props) {
  return (
    <motion.aside
      initial={{ x: "100%" }}
      animate={{ x: open ? "0%" : "100%" }}
      transition={{ type: "spring", stiffness: 120, damping: 18 }}
      className="fixed top-0 right-0 h-full w-[min(480px,90vw)] bg-slate-900/95 border-l border-white/10 p-4 overflow-auto z-30"
    >
      <h2 className="text-lg mb-3">Venue Map</h2>
      <div
        className="venue-map [&_polygon]:cursor-pointer"
        dangerouslySetInnerHTML={{ __html: svgMarkup }}
        onClick={(e) => {
          const target = e.target as SVGElement;
          const id = target.id || target.getAttribute("data-zone-id");
          if (id) onSelectZone(id);
        }}
      />
      {highlights.length > 0 && (
        <p className="text-xs text-cyan-300 mt-2">Highlighted: {highlights.join(", ")}</p>
      )}
    </motion.aside>
  );
}
