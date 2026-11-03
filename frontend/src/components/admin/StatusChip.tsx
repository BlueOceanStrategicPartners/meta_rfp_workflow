import type { ReactNode } from "react";
import { statusMeta, type StatusTone } from "../../lib/adminFormat";

/** RFP status → fixed label + tone (mapping lives in adminFormat.ts). */
export default function StatusChip({ status }: { status: string | null | undefined }) {
  const meta = statusMeta(status);
  return (
    <span className={`admin-chip admin-chip--${meta.tone}`} title={String(status || "")}>
      {meta.label}
    </span>
  );
}

/** Generic chip for non-status labels ("You're live", "Booked", "Over"). */
export function Chip({
  tone = "slate",
  children,
  plain,
}: {
  tone?: StatusTone | "red";
  children: ReactNode;
  plain?: boolean;
}) {
  return <span className={`admin-chip admin-chip--${tone} ${plain ? "admin-chip--plain" : ""}`}>{children}</span>;
}
