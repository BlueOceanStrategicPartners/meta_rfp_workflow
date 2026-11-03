import type { AuditEvent } from "../../lib/adminApi";
import { actionLabel, formatDateTime, formatRelativeTime } from "../../lib/adminFormat";

function payloadSummary(e: AuditEvent): string | null {
  const p = e.payload;
  if (!p || typeof p !== "object") return null;
  if (typeof p.text === "string") return `“${p.text}”`;
  if (typeof p.message === "string") return `“${p.message}”`;
  if (typeof p.note === "string" && p.note) return `Note: ${p.note}`;
  if (p.fields && typeof p.fields === "object") {
    const keys = Object.keys(p.fields as object);
    if (keys.length) return `Fields: ${keys.join(", ").replace(/_/g, " ")}`;
  }
  if (typeof p.previous_status === "string") return `Was ${p.previous_status.toLowerCase().replace(/_/g, " ")}`;
  if (typeof p.created === "number") return `${p.created} added, ${p.updated ?? 0} updated, ${p.skipped ?? 0} skipped`;
  return null;
}

/** Audit events as a readable list: what happened, who did it, when. */
export default function ActivityList({
  events,
  empty,
  showDetails = true,
}: {
  events: AuditEvent[];
  empty: string;
  showDetails?: boolean;
}) {
  if (!events.length) return <div className="studio-empty-list">{empty}</div>;
  return (
    <ul className="divide-y divide-[color:var(--admin-line)]">
      {events.map((e, i) => {
        const detail = showDetails ? payloadSummary(e) : null;
        return (
          <li key={e.id ?? `${e.action}-${e.created_at}-${i}`} className="flex items-start justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="admin-fg text-sm">{actionLabel(e.action)}</p>
              <p className="admin-faint truncate text-xs">
                {e.actor ?? "System"}
                {detail ? <span className="admin-muted"> · {detail}</span> : null}
              </p>
            </div>
            <time
              className="admin-faint admin-num shrink-0 text-xs"
              dateTime={e.created_at}
              title={formatDateTime(e.created_at)}
            >
              {formatRelativeTime(e.created_at)}
            </time>
          </li>
        );
      })}
    </ul>
  );
}
