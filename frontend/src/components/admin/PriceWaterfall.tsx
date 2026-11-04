import { useMemo } from "react";
import type { Money, QuoteExplanationStep } from "../../lib/adminApi";
import { formatMoney } from "../../lib/adminFormat";
import {
  buildWaterfall,
  formatSignedMoney,
  scalePct,
  waterfallMismatch,
  type WaterfallDirection,
  type WaterfallRow,
} from "../../lib/adminPricing";
import AdminTable from "./AdminTable";

const LEGEND: { direction: WaterfallDirection; label: string }[] = [
  { direction: "up", label: "Raises the price" },
  { direction: "down", label: "Lowers the price" },
  { direction: "total", label: "Starting price and totals" },
];

function amountText(r: WaterfallRow): string {
  return r.direction === "base" || r.isTotal ? formatMoney(r.amount) : formatSignedMoney(r.amount);
}

/**
 * Horizontal waterfall from the base price to the opening offer (XGBoost plan §3 D3).
 * Every bar sits on one linear scale from 0 to the largest running total, so lengths compare honestly.
 * The rows are plain text (label, signed amount, price so far) and colour is never the only cue.
 */
export default function PriceWaterfall({
  steps,
  target,
  anchor,
}: {
  steps: QuoteExplanationStep[];
  /** Saved prices, used to warn if the steps don't add up to them. */
  target?: Money | null;
  anchor?: Money | null;
}) {
  const wf = useMemo(() => buildWaterfall(steps), [steps]);

  if (!wf.rows.length) {
    return <div className="studio-empty-list">No price steps were saved for this quote.</div>;
  }

  const gridSize = wf.max > 0 ? `${(wf.tickStep / wf.max) * 100}% 100%` : undefined;
  const mismatch = waterfallMismatch(wf, { target, anchor });

  return (
    <div className="space-y-3">
      {mismatch ? (
        <p className="admin-alert admin-alert--warning">
          These steps don't add up exactly to the saved price. The saved prices above are the ones the agent uses.
        </p>
      ) : null}
      <ul className="admin-muted flex flex-wrap gap-x-4 gap-y-1 text-[11px]" aria-label="Colour key">
        {LEGEND.map((l) => (
          <li key={l.direction} className="inline-flex items-center gap-1.5">
            <span className={`admin-wf-swatch admin-wf-bar--${l.direction}`} aria-hidden />
            {l.label}
          </li>
        ))}
      </ul>

      <ol className="admin-wf" aria-label="How the price was built, step by step">
        {wf.rows.map((r) => {
          const amount = amountText(r);
          const soFar = formatMoney(r.end);
          const showSoFar = !r.isTotal && r.direction !== "base";
          return (
            <li
              key={r.id}
              className={`admin-wf-row ${r.isTotal ? "is-total" : ""}`}
              title={showSoFar ? `${r.label}: ${amount} (price so far ${soFar})` : `${r.label}: ${amount}`}
            >
              <span className="admin-wf-label">{r.label}</span>
              <span className="admin-wf-track" style={gridSize ? { backgroundSize: gridSize } : undefined} aria-hidden>
                <span
                  className={`admin-wf-bar admin-wf-bar--${r.direction}`}
                  style={{ left: `${r.leftPct}%`, width: `${r.widthPct}%` }}
                />
              </span>
              <span className="admin-wf-amount">
                {amount}
                {showSoFar ? <span className="admin-sr-only">, price so far {soFar}</span> : null}
              </span>
            </li>
          );
        })}
      </ol>

      {wf.ticks.length > 1 ? (
        <div className="admin-wf-axis" aria-hidden>
          <div className="admin-wf-ticks">
            {wf.ticks.map((t) => {
              const pct = scalePct(t, wf.max);
              return (
                <span key={t} className={pct > 85 ? "is-end" : ""} style={{ left: `${pct}%` }}>
                  {formatMoney(t)}
                </span>
              );
            })}
          </div>
        </div>
      ) : null}

      <details className="text-xs">
        <summary className="admin-link cursor-pointer select-none !no-underline">Show the steps as a table</summary>
        <div className="mt-2">
          <AdminTable
            caption="Price steps"
            columns={[
              { key: "step", header: "Step", render: (r: WaterfallRow) => r.label },
              { key: "change", header: "Change", numeric: true, render: (r: WaterfallRow) => amountText(r) },
              { key: "total", header: "Price so far", numeric: true, render: (r: WaterfallRow) => formatMoney(r.end) },
            ]}
            rows={wf.rows}
            rowKey={(r) => r.id}
            empty="No steps."
          />
        </div>
      </details>
    </div>
  );
}
