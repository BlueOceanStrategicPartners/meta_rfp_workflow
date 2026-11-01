import { AnimatePresence, motion } from "framer-motion";

const PHASES = [
  "Reading your brief and attachments…",
  "Muse Spark is restructuring the HTML layout…",
  "Applying typography, spacing, and responsive rules…",
  "Binding RFP proposal fields and media…",
  "Polishing interactions and CTA visibility…",
  "Preparing live preview output…",
] as const;

type Props = {
  active: boolean;
  phaseIndex: number;
  previewDoc: string;
};

export function designerAgentPhaseCount() {
  return PHASES.length;
}

export function designerAgentPhaseLabel(index: number) {
  return PHASES[Math.min(index, PHASES.length - 1)];
}

export default function DesignerAgentProgress({ active, phaseIndex, previewDoc }: Props) {
  const label = designerAgentPhaseLabel(phaseIndex);

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
          className="max-w-[min(100%,22rem)] rounded-2xl border border-violet-400/30 bg-gradient-to-br from-violet-950/50 to-[#0c1220]/80 p-3 shadow-lg shadow-violet-900/20"
        >
          <div className="mb-2 flex items-start gap-2">
            <span className="mt-1 flex h-2 w-2 shrink-0 animate-pulse rounded-full bg-fuchsia-400 shadow-[0_0_8px_rgba(232,121,249,0.8)]" />
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-violet-200/80">
                Design Agent working
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
              title="Work in progress preview"
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
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-violet-900/5 to-violet-950/25" />
            <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-white/10">
              <motion.div
                className="h-full w-1/3 bg-gradient-to-r from-transparent via-violet-400 to-transparent"
                animate={{ x: ["-120%", "320%"] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
              />
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
