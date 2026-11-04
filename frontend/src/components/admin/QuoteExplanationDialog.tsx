import { Fragment, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { usePolling } from "../../hooks/usePolling";
import {
  AdminApiError,
  getQuoteExplanation,
  type QuoteExplanation,
  type QuoteWithRfp,
} from "../../lib/adminApi";
import { formatDateTime, formatMoney } from "../../lib/adminFormat";
import {
  describeInputs,
  engineLabel,
  fallbackReasonText,
  formatSignedMoney,
  usedModel,
} from "../../lib/adminPricing";
import TemplateIconButton from "../designer/TemplateIconButton";
import { IconAlert, IconClose } from "./AdminIcons";
import LoadState from "./LoadState";
import PriceLadder from "./PriceLadder";
import PriceWaterfall from "./PriceWaterfall";
import { Chip } from "./StatusChip";

type Props = {
  /** The quote row that was clicked; `null` keeps the dialog closed. */
  quote: QuoteWithRfp | null;
  onClose: () => void;
};

const FOCUSABLE =
  'a[href], button:not([disabled]), summary, input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Keep Tab inside the dialog. */
function trapTab(e: KeyboardEvent, root: HTMLElement | null) {
  if (!root) return;
  const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.getClientRects().length > 0,
  );
  if (!items.length) {
    e.preventDefault();
    return;
  }
  const first = items[0];
  const last = items[items.length - 1];
  const active = document.activeElement;
  if (e.shiftKey && (active === first || !root.contains(active))) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && (active === last || !root.contains(active))) {
    e.preventDefault();
    first.focus();
  }
}

function Note({ children }: { children: string }) {
  return (
    <p className="admin-alert admin-alert--warning flex items-start gap-2">
      <span className="mt-0.5 shrink-0" aria-hidden>
        <IconAlert />
      </span>
      <span>{children}</span>
    </p>
  );
}

function NoBreakdown() {
  return (
    <div className="studio-empty-list">
      No breakdown was saved for this quote. Quotes made before the new pricing engine don't have one; new quotes
      always do.
    </div>
  );
}

function Explanation({ exp }: { exp: QuoteExplanation }) {
  const lines = describeInputs(exp.inputs);
  const warnings = (exp.inputs?.warnings ?? []).filter((w) => typeof w === "string" && w.trim());
  const floorSteps = exp.floor_steps ?? [];
  const floorTotal = exp.floor ?? floorSteps[floorSteps.length - 1]?.running_total ?? null;
  const steps = exp.steps ?? [];

  if (!steps.length && !lines.length) {
    return (
      <div className="space-y-5">
        <PriceLadder floor={exp.floor} target={exp.target} anchor={exp.anchor} numbersOnly />
        <NoBreakdown />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PriceLadder floor={exp.floor} target={exp.target} anchor={exp.anchor} numbersOnly />

      <section aria-labelledby="qx-inputs">
        <h4 id="qx-inputs" className="admin-section-title mb-2">
          What the client asked for
        </h4>
        <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-y-2">
          {lines.map((l) => (
            <Fragment key={l.label}>
              <dt className="admin-muted text-xs sm:pt-0.5">{l.label}</dt>
              <dd className="admin-fg admin-num mb-1.5 text-sm sm:mb-0">{l.value}</dd>
            </Fragment>
          ))}
        </dl>
        {exp.inputs?.dates_assumed || warnings.length ? (
          <div className="mt-3 space-y-2">
            {exp.inputs?.dates_assumed ? <Note>Dates not confirmed — this is an estimate.</Note> : null}
            {warnings.map((w, i) => (
              <Note key={`${i}:${w}`}>{w}</Note>
            ))}
          </div>
        ) : null}
      </section>

      <section aria-labelledby="qx-steps">
        <h4 id="qx-steps" className="admin-section-title">
          How we got to the price
        </h4>
        <p className="admin-faint mb-3 mt-0.5 text-xs">
          From the base price to the goal price, then the opening offer the client sees.
        </p>
        <PriceWaterfall steps={steps} target={exp.target} anchor={exp.anchor} />
      </section>

      <section className="admin-card p-4" aria-labelledby="qx-floor">
        <h4 id="qx-floor" className="admin-section-title">
          Lowest price (floor)
        </h4>
        <p className="admin-faint mt-0.5 text-xs">
          The lowest price the agent may ever accept. Never shown to the client.
        </p>
        <dl className="mt-3 space-y-1.5 text-sm">
          {floorSteps.map((s, i) => (
            <div key={`${i}:${s.key}`} className="flex items-baseline justify-between gap-3">
              <dt className="admin-muted min-w-0">{s.label}</dt>
              <dd className="admin-fg admin-num whitespace-nowrap">
                {i === 0 ? formatMoney(s.amount) : formatSignedMoney(s.amount)}
              </dd>
            </div>
          ))}
          <div
            className={`flex items-baseline justify-between gap-3 font-semibold ${
              floorSteps.length ? "admin-divider pt-1.5" : ""
            }`}
          >
            <dt className="admin-fg">Floor</dt>
            <dd className="admin-fg admin-num whitespace-nowrap">{formatMoney(floorTotal)}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

/** "Why this price?" for one quote: inputs, waterfall and floor (XGBoost plan §9). */
export default function QuoteExplanationDialog({ quote, onClose }: Props) {
  const quoteId = quote?.id ?? null;
  const expQ = usePolling(
    () => (quoteId ? getQuoteExplanation(quoteId) : Promise.resolve(null)),
    0,
    [quoteId],
  );
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Focus moves into the dialog, Tab stays inside, Esc closes, and focus returns to the row.
  useEffect(() => {
    if (!quoteId) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current();
      } else if (e.key === "Tab") {
        trapTab(e, dialogRef.current);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [quoteId]);

  if (!quote) return null;

  const exp = expQ.data;
  const company = exp?.company_name ?? quote.company_name ?? "Unnamed";
  const created = exp?.created_at ?? quote.created_at;
  const engineSource = exp ?? quote;
  const reason = usedModel(engineSource)
    ? null
    : fallbackReasonText(engineSource.fallback_reason, engineSource.fallback_reason_label);
  const notFound = expQ.error instanceof AdminApiError && expQ.error.status === 404;

  return (
    <div
      className="admin-modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="admin-modal admin-modal--wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="qx-title"
        aria-describedby="qx-subtitle"
      >
        <header className="studio-panel-header !min-h-0">
          <div className="min-w-0">
            <p className="studio-panel-kicker">Pricing</p>
            <h3 id="qx-title" className="text-lg font-semibold">
              Why this price?
            </h3>
            <p id="qx-subtitle" className="studio-panel-subtitle mt-0.5 truncate">
              {company} · {formatDateTime(created)}
            </p>
          </div>
          <TemplateIconButton label="Close" onClick={onClose} compact>
            <IconClose />
          </TemplateIconButton>
        </header>

        <div className="studio-panel-body studio-scroll min-h-0 flex-1 space-y-5 overflow-y-auto overflow-x-hidden !pb-6 !pt-5">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <span className="admin-muted">Priced by</span>
            <Chip tone={usedModel(engineSource) ? "violet" : "slate"}>{engineLabel(engineSource)}</Chip>
            {reason ? <span className="admin-faint text-xs">{reason}</span> : null}
          </p>

          {exp ? (
            <Explanation exp={exp} />
          ) : notFound ? (
            <NoBreakdown />
          ) : (
            <LoadState
              loading={expQ.loading || expQ.refreshing}
              error={expQ.error}
              onRetry={() => void expQ.reload()}
              errorTitle="We couldn't load this explanation."
              loadingText="Loading the price breakdown…"
            />
          )}
        </div>

        <footer className="studio-panel-footer flex flex-wrap items-center justify-end gap-2">
          <Link
            to={`/admin/debates/${encodeURIComponent(exp?.rfp_id ?? quote.rfp_id)}`}
            className="studio-btn-secondary mr-auto"
          >
            Open request
          </Link>
          <button ref={closeRef} type="button" className="studio-btn-secondary" onClick={onClose}>
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}
