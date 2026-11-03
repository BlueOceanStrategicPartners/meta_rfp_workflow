import { formatMoney } from "../../lib/adminFormat";

type Props = {
  floor: string | number | null | undefined;
  target: string | number | null | undefined;
  anchor: string | number | null | undefined;
  agreed?: string | number | null;
  /** Hide the bar, keep the numbers. */
  numbersOnly?: boolean;
};

function num(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

const STEPS = [
  { key: "floor", label: "Floor", color: "#f87171", hint: "Lowest price we'll accept" },
  { key: "target", label: "Target", color: "#34d399", hint: "Price we aim for" },
  { key: "anchor", label: "Anchor", color: "#a78bfa", hint: "Opening offer" },
] as const;

/** Floor · target · anchor (and agreed, if any) with a small position bar. */
export default function PriceLadder({ floor, target, anchor, agreed, numbersOnly }: Props) {
  const values = { floor: num(floor), target: num(target), anchor: num(anchor) };
  const agreedN = num(agreed ?? null);
  const known = [values.floor, values.target, values.anchor, agreedN].filter((v): v is number => v !== null);
  const min = known.length ? Math.min(...known) : 0;
  const max = known.length ? Math.max(...known) : 0;
  const span = max - min;
  // Pad the range so the end dots aren't clipped.
  const pos = (v: number) => (span > 0 ? 6 + ((v - min) / span) * 88 : 50);
  const ordered =
    values.floor !== null && values.target !== null && values.anchor !== null
      ? values.floor <= values.target && values.target <= values.anchor
      : true;

  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-3 gap-2">
        {STEPS.map((s) => (
          <div key={s.key} className="admin-card min-w-0 px-3 py-2" title={s.hint}>
            <dt className="admin-muted flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} aria-hidden />
              {s.label}
            </dt>
            <dd className="admin-num mt-0.5 truncate text-sm font-semibold">{formatMoney(values[s.key])}</dd>
          </div>
        ))}
      </dl>
      {agreedN !== null ? (
        <p className="admin-muted text-xs">
          Agreed price: <span className="admin-fg admin-num font-semibold">{formatMoney(agreedN)}</span>
        </p>
      ) : null}
      {!numbersOnly && known.length >= 2 ? (
        <div className="admin-bar-track !h-2.5 !overflow-visible" aria-hidden>
          {STEPS.map((s) =>
            values[s.key] !== null ? (
              <span
                key={s.key}
                className="admin-ladder-dot"
                style={{ left: `${pos(values[s.key]!)}%`, background: s.color }}
              />
            ) : null,
          )}
          {agreedN !== null ? (
            <span
              className="admin-ladder-dot"
              style={{ left: `${pos(agreedN)}%`, background: "#fbbf24", width: "0.6rem", height: "0.6rem" }}
            />
          ) : null}
        </div>
      ) : null}
      {!ordered ? (
        <p className="admin-warning-text text-xs">Check this quote: the floor is above the target or anchor.</p>
      ) : null}
    </div>
  );
}
