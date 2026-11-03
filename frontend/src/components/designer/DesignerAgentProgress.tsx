import { AnimatePresence, motion } from "framer-motion";
import type { AgentProgressItem, AgentWorkPlanStep } from "../../lib/designerChatStream";
import { isPlanningOnlyTodos } from "../../lib/designerAgentTodos";
import { normalizeDesignerProgressLabel } from "../../lib/designerUserLabels";

export type AgentContinuationPanel = {
  completed: AgentProgressItem[];
  remaining: string[];
  onContinue: () => void;
  onDismiss?: () => void;
};

type Props = {
  active: boolean;
  steps: AgentWorkPlanStep[];
  tasks?: AgentWorkPlanStep[];
  previewDoc: string;
  /** When false, never mount the WIP iframe (prevents duplicate Tailwind/doc execution). */
  showProgressIframe?: boolean;
  continuation?: AgentContinuationPanel | null;
};

function StepIcon({ status }: { status: AgentWorkPlanStep["status"] }) {
  if (status === "done") {
    return (
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/25 text-emerald-300">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M6 12l4 4 8-8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (status === "active") {
    return (
      <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-fuchsia-400/40" />
        <span className="relative h-2 w-2 rounded-full bg-fuchsia-400 shadow-[0_0_8px_rgba(232,121,249,0.8)]" />
      </span>
    );
  }
  if (status === "skipped") {
    return <span className="h-4 w-4 shrink-0 rounded-full border border-white/15 bg-white/5" aria-hidden />;
  }
  return <span className="h-4 w-4 shrink-0 rounded-full border border-white/20 bg-white/[0.04]" aria-hidden />;
}

function OkIcon({ ok }: { ok: boolean }) {
  if (ok) {
    return (
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/25 text-emerald-300">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M6 12l4 4 8-8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  return (
    <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-amber-300">
      <span className="text-[10px] font-bold leading-none">!</span>
    </span>
  );
}

function PendingIcon() {
  return <span className="h-4 w-4 shrink-0 rounded-full border border-white/25 bg-white/[0.06]" aria-hidden />;
}

export default function DesignerAgentProgress({
  active,
  steps,
  tasks = [],
  previewDoc,
  showProgressIframe = false,
  continuation,
}: Props) {
  const showCard = active || Boolean(continuation);
  const displaySteps =
    tasks.length > 0 && !isPlanningOnlyTodos(tasks)
      ? tasks
      : steps.length > 0
        ? steps
        : tasks;
  const hasTodoList = displaySteps.length > 0;
  const showHeadline = Boolean(continuation) || !hasTodoList;

  const headline = continuation
    ? "Some edits still need attention"
    : normalizeDesignerProgressLabel(
        active ? "Connecting to design agent…" : "Working on your request…",
      );

  return (
    <AnimatePresence>
      {showCard ? (
        <motion.div
          role="status"
          aria-live="polite"
          aria-busy={active ? "true" : "false"}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
          className="studio-agent-progress-card"
        >
          <div className={`flex min-w-0 items-start gap-2 ${hasTodoList && !continuation ? "mb-1" : "mb-2"}`}>
            {continuation ? (
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-500/25 text-amber-200">
                <span className="text-[10px] font-bold">…</span>
              </span>
            ) : hasTodoList ? null : (
              <StepIcon status="active" />
            )}
            <div className="min-w-0 flex-1">
            <p className="studio-progress-kicker">
                {continuation ? "Design Agent — partial completion" : "Your to-do list"}
              </p>
              {showHeadline ? (
                <p className="studio-progress-headline">{headline}</p>
              ) : null}
            </div>
            {continuation?.onDismiss ? (
              <button
                type="button"
                onClick={continuation.onDismiss}
                className="shrink-0 rounded-lg px-1.5 py-0.5 text-[10px] text-white/40 hover:bg-white/10 hover:text-white/70"
                aria-label="Dismiss progress card"
              >
                ×
              </button>
            ) : null}
          </div>

          {continuation ? (
            <div className="mb-2 space-y-2">
              {continuation.completed.length > 0 ? (
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-300/80">
                    Completed
                  </p>
                  <ul className="max-h-32 space-y-1 overflow-y-auto studio-scroll pr-0.5">
                    {continuation.completed.map((item) => (
                      <li
                        key={item.id}
                        className="flex min-w-0 items-start gap-2 rounded-lg px-1.5 py-1 text-[11px] leading-snug text-emerald-100/90"
                      >
                        <OkIcon ok={item.ok} />
                        <span className="min-w-0 break-words [overflow-wrap:anywhere]">{item.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {continuation.remaining.length > 0 ? (
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-white/45">Remaining</p>
                  <ul className="max-h-28 space-y-1 overflow-y-auto studio-scroll pr-0.5">
                    {continuation.remaining.map((item, idx) => (
                      <li
                        key={`rem-${idx}`}
                        className="flex min-w-0 items-start gap-2 rounded-lg px-1.5 py-1 text-[11px] leading-snug text-white/55"
                      >
                        <PendingIcon />
                        <span className="min-w-0 break-words [overflow-wrap:anywhere]">{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <button
                type="button"
                onClick={continuation.onContinue}
                className="mt-1 w-full rounded-xl bg-gradient-to-r from-emerald-600/90 to-teal-600/90 px-3 py-2 text-xs font-semibold text-white shadow-md shadow-emerald-900/30 hover:from-emerald-500 hover:to-teal-500 focus-visible:ring-2 focus-visible:ring-emerald-400"
              >
                Continue — finish the remaining edits
              </button>
            </div>
          ) : (
            <>
              {displaySteps.length > 0 ? (
                <ul className="mb-2 max-h-48 space-y-1.5 overflow-y-auto studio-scroll pr-0.5">
                  {displaySteps.map((step) => (
                    <li
                      key={step.id}
                      className={`flex min-w-0 items-start gap-2 rounded-lg px-1.5 py-1 text-[11px] leading-snug ${
                        step.status === "active"
                          ? "studio-progress-step-active"
                          : step.status === "done"
                            ? "studio-progress-step-done"
                            : step.status === "skipped"
                              ? "studio-progress-step-skipped"
                              : "studio-progress-step-pending"
                      }`}
                    >
                      <StepIcon status={step.status} />
                      <span className="min-w-0 break-words [overflow-wrap:anywhere]">{step.label}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}

          {showProgressIframe && active && !continuation && previewDoc.trim() ? (
            <>
              <p className="studio-progress-hint">
                Live preview updates as each step completes.
              </p>
              <div className="relative aspect-[5/3] overflow-hidden rounded-lg border border-white/10 bg-[#e8e9ed]">
                <iframe
                  title="Work in progress preview"
                  className="studio-template-card-iframe"
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
            </>
          ) : null}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
