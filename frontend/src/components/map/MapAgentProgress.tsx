import { AnimatePresence, motion } from "framer-motion";

const PHASES = [
  "Reading floorplan image and venue brief…",
  "Muse Spark is tracing interactive zones…",
  "Binding labels, descriptions, and photo galleries…",
  "Wiring click popups and parent postMessage hooks…",
  "Validating location ids against markup…",
  "Preparing live map preview…",
] as const;

type Props = {
  active: boolean;
  phaseIndex: number;
  previewDoc: string;
};

export function mapAgentPhaseCount() {
  return PHASES.length;
}

export function mapAgentPhaseLabel(index: number) {
  return PHASES[Math.min(index, PHASES.length - 1)];
}

export default function MapAgentProgress({ active, phaseIndex, previewDoc }: Props) {
  const label = mapAgentPhaseLabel(phaseIndex);

  return (
    <AnimatePresence>
      {active ? (
        <motion.div
          role="status"
          aria-live="polite"
          aria-busy="true"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
          className="max-w-[min(100%,22rem)] rounded-2xl border border-cyan-400/30 bg-gradient-to-br from-cyan-950/50 to-[#0c1220]/80 p-3 shadow-lg shadow-cyan-900/20"
        >
          <div className="mb-2 flex items-start gap-2">
            <span className="mt-1 flex h-2 w-2 shrink-0 animate-pulse rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-cyan-200/80">
                Map Agent working
              </p>
              <AnimatePresence mode="wait">
                <motion.p
                  key={label}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="text-xs leading-snug text-white/85"
                >
                  {label}
                </motion.p>
              </AnimatePresence>
            </div>
          </div>
          <p className="mb-1.5 text-[10px] text-white/40">
            Draft on canvas below — Live preview updates when finished.
          </p>
          <div className="relative aspect-[5/3] overflow-hidden rounded-lg border border-white/10 bg-[#e8e9ed]">
            <iframe
              title="Work in progress map preview"
              className="pointer-events-none absolute left-0 top-0 border-0 bg-white"
              style={{
                width: "400%",
                height: "400%",
                transform: "scale(0.25)",
                transformOrigin: "top left",
              }}
              sandbox="allow-scripts allow-same-origin"
              srcDoc={previewDoc}
            />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-cyan-900/5 to-cyan-950/25" />
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
