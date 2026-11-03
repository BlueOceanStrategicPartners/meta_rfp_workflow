import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";
import { Link, useParams } from "react-router-dom";
import ActivityList from "../../components/admin/ActivityList";
import AdminConfirm from "../../components/admin/AdminConfirm";
import AdminPanel from "../../components/admin/AdminPanel";
import AdminTable, { type AdminColumn } from "../../components/admin/AdminTable";
import { IconBack, IconRefresh } from "../../components/admin/AdminIcons";
import { useAdminFeedback } from "../../components/admin/AdminLayout";
import LoadState from "../../components/admin/LoadState";
import StatusChip, { Chip } from "../../components/admin/StatusChip";
import { usePolling } from "../../hooks/usePolling";
import {
  AdminApiError,
  errorMessage,
  getRfp,
  listSpaces,
  overrideRfp,
  type DebateRound,
  type ExtractedValue,
  type OverrideField,
  type Quote,
  type RfpDetail,
} from "../../lib/adminApi";
import {
  EMPTY,
  collectQuotes,
  displayValue,
  fieldLabel,
  formatDateTime,
  formatDuration,
  formatMoney,
  formatMs,
  formatPct,
  highlightSegments,
  overCapacityMessage,
  shortId,
} from "../../lib/adminFormat";

/* ---------------- Source ---------------- */

function SourcePanel({ detail }: { detail: RfpDetail }) {
  const text = detail.source_document_text || "";
  const segments = useMemo(() => {
    const quotes = new Set<string>();
    for (const r of detail.rounds ?? []) collectQuotes(r.extraction, quotes);
    return highlightSegments(text, quotes);
  }, [detail.rounds, text]);
  const marked = segments.filter((s) => s.mark).length;

  return (
    <section className="admin-card flex min-h-0 flex-col p-4" aria-labelledby="dd-source">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="dd-source" className="admin-section-title">
          What the client sent
        </h3>
        {text ? (
          <span className="admin-faint text-[11px]">
            {marked ? (
              <>
                <mark className="admin-mark">Highlighted</mark> text was quoted by the agents
              </>
            ) : (
              "No quotes matched the text"
            )}
          </span>
        ) : null}
      </div>
      {text ? (
        <div className="studio-scroll max-h-[50vh] overflow-auto pr-1 xl:max-h-[70vh]">
          <pre className="admin-pre">
            {segments.map((s, i) =>
              s.mark ? (
                <mark key={i} className="admin-mark">
                  {s.text}
                </mark>
              ) : (
                <span key={i}>{s.text}</span>
              ),
            )}
          </pre>
        </div>
      ) : (
        <div className="studio-empty-list">No source text was saved for this request.</div>
      )}
    </section>
  );
}

/* ---------------- Rounds ---------------- */

function severityTone(sev: string): "red" | "amber" | "slate" {
  const s = sev.toLowerCase();
  if (s === "high" || s === "critical") return "red";
  if (s === "medium") return "amber";
  return "slate";
}

function RoundsPanel({ rounds }: { rounds: DebateRound[] }) {
  return (
    <section className="admin-card p-4" aria-labelledby="dd-rounds">
      <h3 id="dd-rounds" className="admin-section-title mb-3">
        Agent check rounds
      </h3>
      {rounds.length === 0 ? (
        <div className="studio-empty-list">No rounds yet. They appear as soon as the agents start reading the request.</div>
      ) : (
        <ol className="space-y-3">
          {rounds.map((r) => (
            <li key={r.iteration} className="border-l-2 border-[color:var(--admin-line)] pl-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="admin-fg text-sm font-semibold">Round {r.iteration}</span>
                <span className="admin-muted admin-num text-xs">Agreement {formatPct(r.consensus)}</span>
                <span className="admin-muted admin-num text-xs">{formatMs(r.duration_ms)}</span>
              </div>
              <p className="admin-faint mt-0.5 text-[11px]">
                Reader: {r.extractor_model_id || EMPTY} · Checker: {r.critic_model_id || EMPTY}
              </p>
              {r.flags?.length ? (
                <ul className="mt-2 space-y-1.5">
                  {r.flags.map((f, i) => (
                    <li key={`${f.field_path}-${i}`} className="text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <Chip tone={severityTone(f.severity || "")}>{fieldLabel(f.field_path)}</Chip>
                        <span className="admin-muted capitalize">{f.severity || "note"}</span>
                        {f.expected != null || f.actual != null ? (
                          <span className="admin-fg admin-num">
                            {f.expected ?? EMPTY} <span className="admin-faint">→</span> {f.actual ?? EMPTY}
                          </span>
                        ) : null}
                      </div>
                      {f.message ? <p className="admin-muted mt-0.5">{f.message}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="admin-success-text mt-1.5 text-xs">No issues found in this round.</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/* ---------------- Extracted fields ---------------- */

type FieldRow = { key: string; value: string; quote: string | null; amber: boolean };

function asExtracted(v: unknown): ExtractedValue | null {
  if (v && typeof v === "object" && !Array.isArray(v) && "value" in (v as object)) return v as ExtractedValue;
  return null;
}

const FIELD_COLUMNS: AdminColumn<FieldRow>[] = [
  {
    key: "field",
    header: "Field",
    className: "whitespace-nowrap",
    render: (r) => (
      <span className="flex items-center gap-1.5">
        <span className="font-medium">{fieldLabel(r.key)}</span>
        {r.amber ? <Chip tone="amber">Check</Chip> : null}
      </span>
    ),
  },
  { key: "value", header: "Value", render: (r) => <span className="break-words">{r.value}</span> },
  {
    key: "quote",
    header: "Quoted from source",
    render: (r) =>
      r.quote ? (
        <span className="admin-muted block min-w-[8rem] italic">“{r.quote}”</span>
      ) : (
        <span className="admin-faint">{EMPTY}</span>
      ),
  },
];

function FieldsPanel({ detail }: { detail: RfpDetail }) {
  const latest = detail.rounds?.length ? detail.rounds[detail.rounds.length - 1] : null;
  const amber = new Set(detail.amber_fields ?? []);
  const rows: FieldRow[] = Object.entries(latest?.extraction ?? {}).map(([key, raw]) => {
    const ev = asExtracted(raw);
    const value = ev ? ev.value : raw;
    const quote = ev?.source_citation?.verbatim_quote ?? null;
    const isAmber = amber.has(key) || [...amber].some((a) => a.startsWith(`${key}.`) || a.endsWith(`.${key}`));
    return { key, value: displayValue(value), quote, amber: isAmber };
  });

  return (
    <section className="admin-card p-4" aria-labelledby="dd-fields">
      <h3 id="dd-fields" className="admin-section-title mb-3">
        Details the agents found
      </h3>
      <AdminTable
        caption="Extracted fields"
        columns={FIELD_COLUMNS}
        rows={rows}
        rowKey={(r) => r.key}
        rowClassName={(r) => (r.amber ? "admin-amber-outline" : "")}
        empty="No details extracted yet. They appear after the first check round."
        maxHeight="22rem"
      />
    </section>
  );
}

/* ---------------- Override ---------------- */

const SEATING = ["banquet", "classroom", "theater", "u_shape", "cocktail"];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

type OverrideForm = Record<OverrideField, string>;

function str(v: unknown): string {
  return v === null || v === undefined ? "" : String(v);
}

function formFromCards(detail: RfpDetail): OverrideForm {
  const ov = detail.cards?.event_overview ?? {};
  const room = detail.cards?.room_block ?? {};
  const meeting = detail.cards?.meeting_space ?? {};
  return {
    company_name: str(ov.company_name),
    event_type: str(ov.event_type),
    check_in_date: str(ov.check_in_date),
    check_out_date: str(ov.check_out_date),
    total_room_nights: str(room.total_room_nights),
    headcount: str(meeting.headcount),
    seating_style: str(meeting.seating_style).toLowerCase(),
  };
}

function validateOverride(f: OverrideForm, initial: OverrideForm): Partial<Record<OverrideField, string>> {
  const e: Partial<Record<OverrideField, string>> = {};
  for (const k of ["total_room_nights", "headcount"] as const) {
    if (f[k] === initial[k] || f[k].trim() === "") continue;
    const n = Number(f[k]);
    if (!Number.isInteger(n) || n < 1) e[k] = "Whole number, 1 or more.";
  }
  for (const k of ["check_in_date", "check_out_date"] as const) {
    if (f[k] !== initial[k] && f[k] && !DATE_RE.test(f[k])) e[k] = "Pick a date.";
  }
  if (!e.check_in_date && !e.check_out_date && DATE_RE.test(f.check_in_date) && DATE_RE.test(f.check_out_date)) {
    if (f.check_out_date <= f.check_in_date) e.check_out_date = "Check-out must be after check-in.";
  }
  if (f.company_name !== initial.company_name && !f.company_name.trim()) e.company_name = "Company can't be empty.";
  return e;
}

const OVERRIDE_FORM_ID = "debate-override-form";

function OverridePanel({
  detail,
  form,
  setForm,
  note,
  setNote,
  errors,
  formError,
}: {
  detail: RfpDetail;
  form: OverrideForm;
  setForm: (updater: (f: OverrideForm) => OverrideForm) => void;
  note: string;
  setNote: (v: string) => void;
  errors: Partial<Record<OverrideField, string>>;
  formError: string | null;
}) {
  const amber = new Set(detail.amber_fields ?? []);
  const field = (key: OverrideField, label: string, input: ReactElement) => (
    <label className="block min-w-0">
      <span className="admin-label flex items-center gap-1.5">
        {label}
        {amber.has(key) ? <Chip tone="amber">Check</Chip> : null}
      </span>
      {input}
      {errors[key] ? <span className="admin-danger-text mt-1 block text-xs">{errors[key]}</span> : null}
    </label>
  );
  const cls = (key: OverrideField) =>
    `studio-field ${errors[key] ? "admin-field-invalid" : ""} ${amber.has(key) ? "admin-amber-outline" : ""}`;
  const set = (key: OverrideField) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  const seatingOptions = SEATING.includes(form.seating_style) || !form.seating_style
    ? SEATING
    : [form.seating_style, ...SEATING];

  return (
    <section className="admin-card p-4" aria-labelledby="dd-override">
      <h3 id="dd-override" className="admin-section-title">
        Correct the details
      </h3>
      <p className="admin-muted mb-3 mt-0.5 text-xs">
        Changes go straight to the client's cards and the quote is recalculated.
      </p>
      {formError ? (
        <p className="admin-alert mb-3" role="alert">
          {formError}
        </p>
      ) : null}
      <form id={OVERRIDE_FORM_ID} className="grid gap-3 sm:grid-cols-2" noValidate onSubmit={(e) => e.preventDefault()}>
        {field("company_name", "Company", <input className={cls("company_name")} value={form.company_name} onChange={set("company_name")} />)}
        {field("event_type", "Event type", <input className={cls("event_type")} value={form.event_type} onChange={set("event_type")} placeholder="e.g. Conference" />)}
        {field(
          "check_in_date",
          "Check-in",
          <input type="date" className={cls("check_in_date")} value={DATE_RE.test(form.check_in_date) ? form.check_in_date : ""} onChange={set("check_in_date")} />,
        )}
        {field(
          "check_out_date",
          "Check-out",
          <input type="date" className={cls("check_out_date")} value={DATE_RE.test(form.check_out_date) ? form.check_out_date : ""} onChange={set("check_out_date")} />,
        )}
        {field(
          "total_room_nights",
          "Room nights",
          <input type="number" min={1} step={1} inputMode="numeric" className={`${cls("total_room_nights")} admin-num`} value={form.total_room_nights} onChange={set("total_room_nights")} />,
        )}
        {field(
          "headcount",
          "Headcount",
          <input type="number" min={1} step={1} inputMode="numeric" className={`${cls("headcount")} admin-num`} value={form.headcount} onChange={set("headcount")} />,
        )}
        {field(
          "seating_style",
          "Seating style",
          <select className={cls("seating_style")} value={form.seating_style} onChange={set("seating_style")}>
            {!form.seating_style ? <option value="">Not set</option> : null}
            {seatingOptions.map((s) => (
              <option key={s} value={s}>
                {fieldLabel(s)}
              </option>
            ))}
          </select>,
        )}
        <label className="block min-w-0 sm:col-span-2">
          <span className="admin-label">Note (optional)</span>
          <input
            className="studio-field"
            value={note}
            maxLength={500}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Confirmed by phone"
          />
        </label>
      </form>
    </section>
  );
}

/* ---------------- Quotes ---------------- */

const QUOTE_COLUMNS: AdminColumn<Quote>[] = [
  {
    key: "created",
    header: "Created",
    render: (q) => <span className="whitespace-nowrap">{formatDateTime(q.created_at)}</span>,
  },
  { key: "floor", header: "Floor", numeric: true, render: (q) => formatMoney(q.floor) },
  { key: "target", header: "Target", numeric: true, render: (q) => formatMoney(q.target) },
  { key: "anchor", header: "Anchor", numeric: true, render: (q) => formatMoney(q.anchor) },
  { key: "agreed", header: "Agreed", numeric: true, render: (q) => formatMoney(q.agreed) },
  {
    key: "engine",
    header: "Engine",
    render: (q) => <Chip tone={q.used_fallback ? "slate" : "violet"}>{q.used_fallback ? "Fallback" : "XGBoost"}</Chip>,
  },
];

/* ---------------- Page ---------------- */

export default function DebateDetailPage() {
  const { rfpId = "" } = useParams();
  const { notify } = useAdminFeedback();
  const { data, error, loading, refreshing, reload } = usePolling(() => getRfp(rfpId), 0, [rfpId]);

  const initial = useMemo(() => (data ? formFromCards(data) : null), [data]);
  const [form, setFormState] = useState<OverrideForm | null>(null);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Reset the form whenever fresh data arrives.
  useEffect(() => {
    if (initial) setFormState(initial);
  }, [initial]);

  const setForm = useCallback((updater: (f: OverrideForm) => OverrideForm) => {
    setFormState((f) => (f ? updater(f) : f));
  }, []);

  const changed = useMemo(() => {
    if (!form || !initial) return {} as Partial<Record<OverrideField, string | number>>;
    const out: Partial<Record<OverrideField, string | number>> = {};
    for (const k of Object.keys(form) as OverrideField[]) {
      if (form[k] === initial[k]) continue;
      if (k === "total_room_nights" || k === "headcount") {
        if (form[k].trim() !== "") out[k] = Number(form[k]);
      } else if (form[k].trim() !== "") {
        out[k] = form[k].trim();
      }
    }
    return out;
  }, [form, initial]);
  const errors = useMemo(() => (form && initial ? validateOverride(form, initial) : {}), [form, initial]);
  const changedCount = Object.keys(changed).length;
  const canSave = changedCount > 0 && Object.keys(errors).length === 0 && !saving;

  const save = async () => {
    setSaving(true);
    setFormError(null);
    try {
      await overrideRfp(rfpId, { fields: changed, note: note.trim() || undefined });
      setConfirmOpen(false);
      setNote("");
      notify("Override saved. Client cards updated.", "success");
      await reload();
    } catch (err) {
      setConfirmOpen(false);
      let message = errorMessage(err, "We couldn't save the override.");
      if (err instanceof AdminApiError && err.alternatives?.length) {
        const names = await alternativeNames(err.alternatives);
        message = overCapacityMessage(err.detail, names);
      }
      setFormError(message);
      notify(message, "error");
    } finally {
      setSaving(false);
    }
  };

  const title = data ? data.cards?.event_overview?.company_name || data.company_name || `Request ${shortId(data.id)}` : "Request";

  return (
    <AdminPanel
      kicker="Module 2 · Debates"
      title={String(title)}
      subtitle={
        data ? (
          <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
            <StatusChip status={data.status} />
            <span>{data.client_email || "No client email"}</span>
            <span aria-hidden>·</span>
            <span>
              {data.sla?.duration_seconds != null
                ? `Answered in ${formatDuration(data.sla.duration_seconds)}`
                : "Not answered yet"}
            </span>
          </span>
        ) : (
          "How the agents read this request, and where you can correct it."
        )
      }
      actions={
        <>
          <Link to="/admin/debates" className="studio-btn-secondary">
            <IconBack />
            All requests
          </Link>
          <button type="button" className="studio-btn-secondary" onClick={() => void reload()} disabled={refreshing}>
            <IconRefresh />
            Refresh
          </button>
        </>
      }
      footer={
        data && form ? (
          <>
            <span className="admin-faint mr-auto text-xs">
              {changedCount
                ? `${changedCount} ${changedCount === 1 ? "change" : "changes"} ready to save`
                : "Change a field above to save an override."}
            </span>
            <button
              type="button"
              className="studio-btn-secondary"
              disabled={!changedCount || saving}
              onClick={() => {
                if (initial) setFormState(initial);
                setFormError(null);
              }}
            >
              Undo changes
            </button>
            <button
              type="button"
              className="studio-btn-secondary admin-btn-primary"
              disabled={!canSave}
              onClick={() => setConfirmOpen(true)}
            >
              Save override
            </button>
          </>
        ) : undefined
      }
    >
      <AdminConfirm
        open={confirmOpen}
        title="Override these fields?"
        message="The client's cards and quote will update."
        confirmLabel="Save override"
        busyLabel="Saving…"
        busy={saving}
        onConfirm={() => void save()}
        onCancel={() => setConfirmOpen(false)}
      />
      {!data ? (
        <LoadState
          loading={loading}
          error={error}
          onRetry={() => void reload()}
          errorTitle="We couldn't load this request."
          loadingText="Loading request…"
        />
      ) : (
        <div className="space-y-4">
          {error ? (
            <div className="admin-alert admin-alert--warning" role="status">
              Couldn't refresh, showing the last data we had. {errorMessage(error)}
            </div>
          ) : null}
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] xl:items-start">
            <div className="min-w-0 xl:sticky xl:top-0">
              <SourcePanel detail={data} />
            </div>
            <div className="min-w-0 space-y-4">
              <RoundsPanel rounds={data.rounds ?? []} />
              <FieldsPanel detail={data} />
              {form ? (
                <OverridePanel
                  detail={data}
                  form={form}
                  setForm={setForm}
                  note={note}
                  setNote={setNote}
                  errors={errors}
                  formError={formError}
                />
              ) : null}
            </div>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <section className="admin-card min-w-0 p-4" aria-labelledby="dd-quotes">
              <h3 id="dd-quotes" className="admin-section-title mb-3">
                Quote history
              </h3>
              <AdminTable
                caption="Quotes for this request"
                columns={QUOTE_COLUMNS}
                rows={data.quotes ?? []}
                rowKey={(q) => q.id}
                empty="No quotes yet. A quote is created once the details are confirmed."
                maxHeight="18rem"
              />
            </section>
            <section className="admin-card min-w-0 p-4" aria-labelledby="dd-audit">
              <h3 id="dd-audit" className="admin-section-title mb-1">
                Admin activity on this request
              </h3>
              <ActivityList events={data.audit ?? []} empty="No admin changes yet. Overrides and takeovers will be listed here." />
            </section>
          </div>
        </div>
      )}
    </AdminPanel>
  );
}

/** Turn alternative space ids from a 400 into names (falls back to short ids). */
async function alternativeNames(alternatives: unknown[]): Promise<string[]> {
  const direct = alternatives
    .map((a) => (a && typeof a === "object" && "name" in (a as object) ? String((a as { name: unknown }).name) : null))
    .filter((n): n is string => !!n);
  if (direct.length) return direct;
  const ids = alternatives.map(String);
  try {
    const spaces = await listSpaces();
    const byId = new Map(spaces.map((s) => [String(s.id), s.name]));
    return ids.map((id) => byId.get(id) ?? shortId(id));
  } catch {
    return ids.map((id) => shortId(id));
  }
}
