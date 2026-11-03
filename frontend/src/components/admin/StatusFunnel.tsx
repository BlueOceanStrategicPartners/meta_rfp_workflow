import { RFP_STATUSES, statusMeta } from "../../lib/adminFormat";

type Props = {
  /** Counts per status; missing statuses count as 0. */
  counts: Record<string, number> | { status: string; count: number }[];
};

/** One horizontal bar per RFP status, in pipeline order, scaled to the largest count. */
export default function StatusFunnel({ counts }: Props) {
  const map: Record<string, number> = Array.isArray(counts)
    ? Object.fromEntries(counts.map((c) => [c.status, c.count]))
    : counts;
  const extra = Object.keys(map).filter((s) => !(RFP_STATUSES as readonly string[]).includes(s));
  const order = [...RFP_STATUSES, ...extra];
  const max = Math.max(1, ...order.map((s) => map[s] ?? 0));

  return (
    <ul className="space-y-2.5">
      {order.map((s) => {
        const count = map[s] ?? 0;
        const meta = statusMeta(s);
        return (
          <li key={s} className="grid grid-cols-[minmax(6.5rem,9rem)_1fr_2.5rem] items-center gap-3">
            <span className="admin-muted truncate text-xs" title={s}>
              {meta.step}
            </span>
            <div className="admin-bar-track" aria-hidden>
              <div
                className={`admin-bar-fill ${count ? "" : "admin-bar-fill--muted"}`}
                style={{ width: `${count ? Math.max(3, (count / max) * 100) : 0}%` }}
              />
            </div>
            <span className="admin-num admin-fg text-right text-xs font-semibold">{count}</span>
          </li>
        );
      })}
    </ul>
  );
}
