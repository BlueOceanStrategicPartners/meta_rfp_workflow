import type { ReactNode } from "react";

type Props = {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  /** Adds a coloured word next to the value, never colour alone. */
  tone?: "default" | "good" | "warn" | "bad";
};

const TONE_CLASS: Record<NonNullable<Props["tone"]>, string> = {
  default: "admin-fg",
  good: "admin-success-text",
  warn: "admin-warning-text",
  bad: "admin-danger-text",
};

export default function StatTile({ label, value, sub, tone = "default" }: Props) {
  return (
    <div className="admin-card min-w-0 px-4 py-3.5">
      <p className="admin-muted truncate text-[11px] font-medium uppercase tracking-wide">{label}</p>
      <p className={`admin-num mt-1.5 truncate text-2xl font-semibold tracking-tight ${TONE_CLASS[tone]}`}>{value}</p>
      {sub ? <p className="admin-faint mt-1 text-xs">{sub}</p> : null}
    </div>
  );
}
