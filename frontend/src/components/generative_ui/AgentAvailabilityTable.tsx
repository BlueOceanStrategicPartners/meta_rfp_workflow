import { motion } from "framer-motion";
import CustomScrollArea from "../ui/CustomScrollArea";

export type AvailabilityTableColumn = {
  key: string;
  label: string;
  align?: "left" | "right";
};

export type AvailabilityTableRow = Record<string, string | number>;

export type AgentAvailabilityTableProps = {
  title: string;
  caption?: string;
  columns: AvailabilityTableColumn[];
  rows: AvailabilityTableRow[];
  highlights?: string[];
  selectedDateIso?: string | null;
  onSelectRow?: (row: AvailabilityTableRow) => void;
  /** Fixed side panel — mirrors RFP summary cards (`right` default; use `left` when cards occupy the right). */
  dockSide?: "left" | "right";
};

function statusClass(status: unknown) {
  const s = String(status || "").toLowerCase();
  if (s === "good") return "client-avail-status client-avail-status--good";
  if (s === "limited") return "client-avail-status client-avail-status--limited";
  return "client-avail-status client-avail-status--tight";
}

const DOCK_BASE =
  "client-side-deck pointer-events-auto fixed top-[4.75rem] bottom-0 z-30 flex w-[min(20rem,calc(100vw-1.5rem))] flex-col gap-2 overflow-y-auto sm:w-80";

export default function AgentAvailabilityTable({
  title,
  caption,
  columns,
  rows,
  highlights = [],
  selectedDateIso,
  onSelectRow,
  dockSide = "right",
}: AgentAvailabilityTableProps) {
  if (!rows.length) return null;

  const slideFrom = dockSide === "left" ? -24 : 24;
  const dockPos = dockSide === "left" ? "left-3 sm:left-4" : "right-3 sm:right-4";

  return (
    <motion.aside
      initial={{ opacity: 0, x: slideFrom }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, ease: [0.45, 0.05, 0.25, 1] }}
      className={`${DOCK_BASE} ${dockPos}`}
      aria-label="Room availability"
    >
      <div className="client-side-deck__header flex items-center justify-between gap-2 px-1">
        <h2 className="client-side-deck__title text-sm font-semibold tracking-tight">Live inventory</h2>
      </div>
      <div className="client-side-card client-side-card--quote client-avail-panel overflow-hidden">
        <div className="client-avail-panel__head border-b px-3 py-2.5 text-left">
          <p className="client-avail-kicker client-side-card__kicker">Guest room windows</p>
          <p className="client-side-card__title text-sm font-semibold">{title}</p>
          {caption ? <p className="client-side-field-hint mt-1 text-[11px]">{caption}</p> : null}
        </div>
        <CustomScrollArea className="client-avail-table-scroll max-h-56" contentClassName="min-h-0">
          <table className="client-avail-table w-full text-left text-[11px]">
            <thead className="client-avail-table__head sticky top-0 text-[10px] uppercase tracking-wide">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={`px-2.5 py-2 font-medium ${col.align === "right" ? "text-right" : ""}`}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const iso = String(row.date_iso || "");
                const selected = selectedDateIso === iso;
                const highlighted = highlights.includes(String(row.date_label));
                return (
                  <tr
                    key={iso || String(row.date_label)}
                    tabIndex={onSelectRow ? 0 : undefined}
                    role={onSelectRow ? "button" : undefined}
                    onClick={() => onSelectRow?.(row)}
                    onKeyDown={(e) => {
                      if (!onSelectRow) return;
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelectRow(row);
                      }
                    }}
                    className={`client-avail-table__row border-t transition ${
                      onSelectRow
                        ? "cursor-pointer hover:bg-cyan-500/10 focus:bg-cyan-500/10 focus:outline-none"
                        : ""
                    } ${selected ? "client-avail-table__row--selected" : highlighted ? "client-avail-table__row--highlight" : ""}`}
                  >
                    {columns.map((col) => {
                      const val = row[col.key];
                      if (col.key === "status") {
                        return (
                          <td key={col.key} className="px-2.5 py-2">
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${statusClass(val)}`}
                            >
                              {String(val)}
                            </span>
                          </td>
                        );
                      }
                      return (
                        <td
                          key={col.key}
                          className={`client-avail-table__cell px-2.5 py-2 ${col.align === "right" ? "text-right tabular-nums" : ""}`}
                        >
                          {col.key === "occupancy_pct" ? `${val}%` : String(val ?? "—")}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CustomScrollArea>
        {onSelectRow ? (
          <p className="client-avail-panel__foot client-side-field-hint border-t px-3 py-2 text-[10px]">
            Tap a date to set your preferred arrival in chat.
          </p>
        ) : null}
      </div>
    </motion.aside>
  );
}
