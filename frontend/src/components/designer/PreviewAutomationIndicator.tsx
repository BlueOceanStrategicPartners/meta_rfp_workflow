type State = "idle" | "running" | "used" | "error";

type Props = {
  state: State;
};

export default function PreviewAutomationIndicator({ state }: Props) {
  if (state === "idle") return null;

  const labels: Record<Exclude<State, "idle">, string> = {
    running: "Running Live preview checks",
    used: "Live preview automation used this turn",
    error: "Preview automation failed — using audit only",
  };

  const colors: Record<Exclude<State, "idle">, string> = {
    running: "text-cyan-300 border-cyan-400/40 bg-cyan-500/10",
    used: "text-emerald-200 border-emerald-400/35 bg-emerald-500/10",
    error: "text-amber-200 border-amber-400/35 bg-amber-500/10",
  };

  const label = labels[state];
  const color = colors[state];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${color}`}
      title={label}
      aria-live="polite"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden className="shrink-0">
        <rect x="3" y="4" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.75" />
        <path d="M8 20h8" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
        {state === "running" && (
          <circle cx="12" cy="10" r="2" fill="currentColor" className="opacity-80" />
        )}
        {state === "used" && (
          <path d="M9 10l2 2 4-4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
        )}
        {state === "error" && (
          <path d="M9 9l6 6M15 9l-6 6" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
        )}
      </svg>
      Preview auto
    </span>
  );
}
