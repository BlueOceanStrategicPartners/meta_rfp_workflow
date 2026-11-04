import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AdminConfirm from "../../components/admin/AdminConfirm";
import AdminPanel from "../../components/admin/AdminPanel";
import AdminTable, { type AdminColumn } from "../../components/admin/AdminTable";
import { IconRefresh } from "../../components/admin/AdminIcons";
import { useAdminFeedback } from "../../components/admin/AdminLayout";
import LoadState from "../../components/admin/LoadState";
import PricingModelCard from "../../components/admin/PricingModelCard";
import QuoteExplanationDialog from "../../components/admin/QuoteExplanationDialog";
import { Chip } from "../../components/admin/StatusChip";
import { usePolling } from "../../hooks/usePolling";
import {
  AdminApiError,
  errorMessage,
  fieldError,
  getPricingModel,
  getPricingPolicy,
  listQuotes,
  listSpaces,
  retrainPricingModel,
  savePricingPolicy,
  type PricingPolicy,
  type QuoteWithRfp,
} from "../../lib/adminApi";
import {
  MONTH_NAMES,
  MONTH_SHORT,
  computeLadderExample,
  formatDateTime,
  formatMoney,
  formatRelativeTime,
  seasonFor,
  shortId,
  validatePolicy,
  type PolicyErrors,
  type PolicyNumbers,
} from "../../lib/adminFormat";
import { engineLabel, fallbackReasonText, retrainFeedback, usedModel } from "../../lib/adminPricing";

/* ---------------- Form model ---------------- */

type PolicyForm = {
  margin: string;
  discount: string;
  target: string;
  anchor: string;
  event: string;
  season: string[]; // 12 entries, multipliers
};

/** Fraction → percent string without float noise: 0.12 → "12". */
function pctString(fraction: number): string {
  return String(Math.round(fraction * 100 * 100) / 100);
}

function formFromPolicy(p: PricingPolicy): PolicyForm {
  return {
    margin: pctString(p.walk_away_floor_margin_pct),
    discount: pctString(p.max_autonomous_discount_pct),
    target: pctString(p.target_markup_pct),
    anchor: pctString(p.anchor_markup_pct),
    event: String(p.event_multiplier),
    season: Array.from({ length: 12 }, (_, i) => String(seasonFor(p.seasonality_json, i + 1))),
  };
}

const n = (s: string) => (s.trim() === "" ? NaN : Number(s));

function policyFromForm(f: PolicyForm): PolicyNumbers {
  const seasonality: Record<string, number> = {};
  f.season.forEach((v, i) => {
    seasonality[String(i + 1)] = n(v);
  });
  return {
    walk_away_floor_margin_pct: n(f.margin) / 100,
    max_autonomous_discount_pct: n(f.discount) / 100,
    target_markup_pct: n(f.target) / 100,
    anchor_markup_pct: n(f.anchor) / 100,
    event_multiplier: n(f.event),
    seasonality_json: seasonality,
  };
}

const SERVER_KEYS: (keyof PolicyNumbers)[] = [
  "walk_away_floor_margin_pct",
  "max_autonomous_discount_pct",
  "target_markup_pct",
  "anchor_markup_pct",
  "event_multiplier",
  "seasonality_json",
];

/* ---------------- Policy section ---------------- */

const PCT_FIELDS: { key: keyof PolicyForm; err: keyof PolicyNumbers; label: string; hint: string }[] = [
  { key: "margin", err: "walk_away_floor_margin_pct", label: "Floor margin %", hint: "Lowest price = base cost plus this margin." },
  {
    key: "discount",
    err: "max_autonomous_discount_pct",
    label: "Max discount %",
    hint: "The most the agent can discount without asking you.",
  },
  { key: "target", err: "target_markup_pct", label: "Target markup %", hint: "The price we aim for. Must be above the floor margin." },
  { key: "anchor", err: "anchor_markup_pct", label: "Anchor markup %", hint: "Opening offer, added on top of the target." },
];

function PolicyEditor({
  form,
  setForm,
  errors,
}: {
  form: PolicyForm;
  setForm: (f: PolicyForm) => void;
  errors: PolicyErrors;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {PCT_FIELDS.map((f) => (
          <label key={f.key} className="block min-w-0">
            <span className="admin-label">{f.label}</span>
            <input
              type="number"
              step="0.5"
              inputMode="decimal"
              className={`studio-field admin-num ${errors[f.err] ? "admin-field-invalid" : ""}`}
              value={form[f.key] as string}
              onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
              aria-invalid={!!errors[f.err]}
            />
            <span className={`mt-1 block text-[11px] ${errors[f.err] ? "admin-danger-text" : "admin-faint"}`}>
              {errors[f.err] ?? f.hint}
            </span>
          </label>
        ))}
        <label className="block min-w-0">
          <span className="admin-label">Event multiplier</span>
          <input
            type="number"
            step="0.05"
            inputMode="decimal"
            className={`studio-field admin-num ${errors.event_multiplier ? "admin-field-invalid" : ""}`}
            value={form.event}
            onChange={(e) => setForm({ ...form, event: e.target.value })}
            aria-invalid={!!errors.event_multiplier}
          />
          <span className={`mt-1 block text-[11px] ${errors.event_multiplier ? "admin-danger-text" : "admin-faint"}`}>
            {errors.event_multiplier ?? "1.0 = normal (0.5 to 3.0). Raise it for city-wide events."}
          </span>
        </label>
      </div>

      <fieldset>
        <legend className="admin-label">Seasonality (price multiplier by month)</legend>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 xl:grid-cols-12">
          {MONTH_SHORT.map((m, i) => {
            const err = errors[`season_${i + 1}`];
            return (
              <label key={m} className="block min-w-0" title={MONTH_NAMES[i]}>
                <span className="admin-muted mb-1 block text-[11px]">{m}</span>
                <input
                  type="number"
                  step="0.05"
                  min={0.5}
                  max={3}
                  inputMode="decimal"
                  aria-label={`${MONTH_NAMES[i]} multiplier`}
                  className={`studio-field admin-num !px-2 text-right ${err ? "admin-field-invalid" : ""}`}
                  value={form.season[i]}
                  onChange={(e) => {
                    const season = [...form.season];
                    season[i] = e.target.value;
                    setForm({ ...form, season });
                  }}
                  aria-invalid={!!err}
                />
              </label>
            );
          })}
        </div>
        <span
          className={`mt-1 block text-[11px] ${
            Object.keys(errors).some((k) => k.startsWith("season_")) || errors.seasonality_json
              ? "admin-danger-text"
              : "admin-faint"
          }`}
        >
          {Object.keys(errors).some((k) => k.startsWith("season_"))
            ? "Each month needs a value from 0.5 to 3.0."
            : (errors.seasonality_json ?? "1.0 = normal. 1.15 = 15% higher that month.")}
        </span>
      </fieldset>
    </div>
  );
}

type ExampleSpace = { name: string; rackRate: number; floorCost: number };

function LadderExampleLine({ policy, space }: { policy: PolicyNumbers; space: ExampleSpace }) {
  const [month, setMonth] = useState(() => new Date().getMonth() + 1);
  const ex = computeLadderExample(policy, space.rackRate, 3, month, space.floorCost);
  return (
    <div className="admin-card px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="admin-section-title">Example quote with these settings</p>
        <label className="admin-muted flex items-center gap-2 text-xs">
          Month
          <select
            className="studio-field !w-auto !py-1.5 text-xs"
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
          >
            {MONTH_NAMES.map((m, i) => (
              <option key={m} value={i + 1}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="admin-fg admin-num mt-2 text-sm">
        {space.name} for 3 nights at {formatMoney(space.rackRate)} → floor <strong>{formatMoney(ex.floor)}</strong> ·
        target <strong>{formatMoney(ex.target)}</strong> · anchor <strong>{formatMoney(ex.anchor)}</strong>
      </p>
      <p className="admin-faint mt-1 text-[11px]">
        Space only, using the simple formula. Real quotes add guest rooms, and a trained model replaces the month
        multiplier. Open a quote below to see exactly how it was priced.
      </p>
    </div>
  );
}

/* ---------------- Quotes table ---------------- */

const QUOTE_COLUMNS: AdminColumn<QuoteWithRfp>[] = [
  {
    key: "rfp",
    header: "Request",
    render: (q) => (
      // The row opens "Why this price?"; the link must not trigger it (click or Enter).
      <Link
        to={`/admin/debates/${encodeURIComponent(q.rfp_id)}`}
        className="admin-link admin-code !no-underline"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        {shortId(q.rfp_id)}
      </Link>
    ),
  },
  {
    key: "company",
    header: "Company",
    render: (q) => <span className="block max-w-[12rem] truncate">{q.company_name || "Unnamed"}</span>,
  },
  { key: "floor", header: "Floor", numeric: true, render: (q) => formatMoney(q.floor) },
  { key: "target", header: "Target", numeric: true, render: (q) => formatMoney(q.target) },
  { key: "anchor", header: "Anchor", numeric: true, render: (q) => formatMoney(q.anchor) },
  { key: "agreed", header: "Agreed", numeric: true, render: (q) => formatMoney(q.agreed) },
  {
    key: "engine",
    header: "Priced by",
    render: (q) => {
      const model = usedModel(q);
      const reason = model ? null : fallbackReasonText(q.fallback_reason, q.fallback_reason_label);
      return (
        <span className="flex min-w-[7.5rem] flex-col items-start gap-0.5">
          <Chip tone={model ? "violet" : "slate"}>{engineLabel(q)}</Chip>
          {reason ? <span className="admin-faint max-w-[12rem] text-[11px] leading-snug">{reason}</span> : null}
        </span>
      );
    },
  },
  {
    key: "created",
    header: "Created",
    render: (q) => (
      <time className="admin-muted whitespace-nowrap text-xs" dateTime={q.created_at} title={formatDateTime(q.created_at)}>
        {formatRelativeTime(q.created_at)}
      </time>
    ),
  },
];

/* ---------------- Page ---------------- */

export default function PricingPage() {
  const { notify } = useAdminFeedback();
  const policyQ = usePolling(getPricingPolicy, 0);
  const modelQ = usePolling(getPricingModel, 0);
  const quotesQ = usePolling(() => listQuotes(), 0);
  const spacesQ = usePolling(() => listSpaces(), 0);

  const [form, setForm] = useState<PolicyForm | null>(null);
  const [serverErrors, setServerErrors] = useState<PolicyErrors>({});
  const [saving, setSaving] = useState(false);
  const [retrainOpen, setRetrainOpen] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [explainQuote, setExplainQuote] = useState<QuoteWithRfp | null>(null);
  const closeExplain = useCallback(() => setExplainQuote(null), []);

  const initialForm = useMemo(() => (policyQ.data ? formFromPolicy(policyQ.data) : null), [policyQ.data]);
  useEffect(() => {
    if (initialForm) setForm(initialForm);
  }, [initialForm]);

  const numbers = useMemo(() => (form ? policyFromForm(form) : null), [form]);
  const clientErrors = useMemo(() => (numbers ? validatePolicy(numbers) : {}), [numbers]);
  const errors: PolicyErrors = { ...serverErrors, ...clientErrors };
  const dirty = !!form && !!initialForm && JSON.stringify(form) !== JSON.stringify(initialForm);
  const valid = Object.keys(clientErrors).length === 0;

  // Example uses the priciest meeting space (rack rate and its floor cost), like the backend's package.
  const exampleSpace = useMemo<ExampleSpace | null>(() => {
    const spaces = (spacesQ.data ?? [])
      .filter((s) => s.space_type !== "ROOM_BLOCK" && Number(s.rack_rate) > 0)
      .sort((a, b) => Number(b.rack_rate) - Number(a.rack_rate));
    const top = spaces[0];
    return top ? { name: top.name, rackRate: Number(top.rack_rate), floorCost: Number(top.base_floor_cost) || 0 } : null;
  }, [spacesQ.data]);

  const save = async () => {
    if (!numbers || !valid) return;
    setSaving(true);
    setServerErrors({});
    try {
      await savePricingPolicy(numbers);
      notify("Pricing policy saved. New quotes will use it.", "success");
      await policyQ.reload();
    } catch (err) {
      if (err instanceof AdminApiError && err.errors) {
        const se: PolicyErrors = {};
        for (const k of SERVER_KEYS) {
          const m = fieldError(err.errors, k);
          if (m) se[k] = m;
        }
        setServerErrors(se);
      }
      notify(errorMessage(err, "We couldn't save the policy."), "error");
    } finally {
      setSaving(false);
    }
  };

  const retrain = async () => {
    setRetraining(true);
    try {
      const res = await retrainPricingModel();
      setRetrainOpen(false);
      const { message, tone } = retrainFeedback(res);
      notify(message, tone);
      await modelQ.reload();
    } catch (err) {
      setRetrainOpen(false);
      notify(errorMessage(err, "Retraining failed. Quotes keep using the simple formula."), "error");
      await modelQ.reload();
    } finally {
      setRetraining(false);
    }
  };

  return (
    <AdminPanel
      kicker="Module 3 · Pricing"
      title="Pricing policy and model"
      subtitle="Set the price ladder the agent negotiates within, and keep the pricing model up to date."
      actions={
        <button
          type="button"
          className="studio-btn-secondary"
          onClick={() => {
            void policyQ.reload();
            void modelQ.reload();
            void quotesQ.reload();
            void spacesQ.reload();
          }}
        >
          <IconRefresh />
          Refresh
        </button>
      }
      footer={
        form ? (
          <>
            <span className="admin-faint mr-auto text-xs">
              {policyQ.data?.updated_at
                ? `Last saved ${formatRelativeTime(policyQ.data.updated_at)}${
                    policyQ.data.updated_by ? ` by ${policyQ.data.updated_by}` : ""
                  }`
                : "Using default settings"}
            </span>
            <button
              type="button"
              className="studio-btn-secondary"
              disabled={!dirty || saving}
              onClick={() => {
                if (initialForm) setForm(initialForm);
                setServerErrors({});
              }}
            >
              Undo changes
            </button>
            <button
              type="button"
              className="studio-btn-secondary admin-btn-primary"
              disabled={!dirty || !valid || saving}
              onClick={() => void save()}
            >
              {saving ? "Saving…" : "Save policy"}
            </button>
          </>
        ) : undefined
      }
    >
      <AdminConfirm
        open={retrainOpen}
        title="Retrain the pricing model?"
        message="It learns from the real occupancy history you've imported (never app-generated days). If the new model beats a simple average, new quotes use it straight away."
        confirmLabel="Retrain model"
        busyLabel="Retraining…"
        busy={retraining}
        onConfirm={() => void retrain()}
        onCancel={() => setRetrainOpen(false)}
      />
      <QuoteExplanationDialog quote={explainQuote} onClose={closeExplain} />
      <div className="space-y-5">
        <section className="admin-card p-4" aria-labelledby="pr-policy">
          <h3 id="pr-policy" className="admin-section-title mb-3">
            Pricing policy
          </h3>
          {!form || !numbers ? (
            <LoadState
              loading={policyQ.loading}
              error={policyQ.error}
              onRetry={() => void policyQ.reload()}
              errorTitle="We couldn't load the pricing policy."
              compact
            />
          ) : (
            <div className="space-y-4">
              <PolicyEditor
                form={form}
                setForm={(f) => {
                  setForm(f);
                  setServerErrors({});
                }}
                errors={errors}
              />
              {!valid ? (
                <p className="admin-alert admin-alert--warning">Fix the highlighted values to see an example quote.</p>
              ) : exampleSpace === null ? (
                <p className="admin-muted text-xs">Add a space in Inventory to see an example quote with your real prices.</p>
              ) : (
                <LadderExampleLine policy={numbers} space={exampleSpace} />
              )}
            </div>
          )}
        </section>

        <PricingModelCard
          model={modelQ.data}
          loading={modelQ.loading}
          error={modelQ.error}
          onRetry={() => void modelQ.reload()}
          onRetrain={() => setRetrainOpen(true)}
          retraining={retraining}
        />

        <section className="admin-card min-w-0 p-4" aria-labelledby="pr-quotes">
          <div className="mb-3">
            <h3 id="pr-quotes" className="admin-section-title">
              Recent quotes
            </h3>
            <p className="admin-faint mt-0.5 text-xs">Select a quote to see why it got that price.</p>
          </div>
          <AdminTable
            caption="Recent quotes. Select a row to see why it got that price."
            columns={QUOTE_COLUMNS}
            rows={quotesQ.data}
            rowKey={(q) => q.id}
            onRowClick={(q) => setExplainQuote(q)}
            rowLabel={(q) => `Why this price? ${q.company_name || "Unnamed"}`}
            selectedKey={explainQuote?.id ?? null}
            loading={quotesQ.loading}
            error={quotesQ.error}
            onRetry={() => void quotesQ.reload()}
            errorTitle="We couldn't load the quotes."
            empty="No quotes yet. Quotes appear here once a client confirms their request details."
            maxHeight="26rem"
          />
        </section>
      </div>
    </AdminPanel>
  );
}
