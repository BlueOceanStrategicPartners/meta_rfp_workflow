import { useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import AdminPanel from "../../components/admin/AdminPanel";
import AdminTable, { type AdminColumn } from "../../components/admin/AdminTable";
import { IconCopy, IconRefresh, IconUpload } from "../../components/admin/AdminIcons";
import { useAdminFeedback } from "../../components/admin/AdminLayout";
import LoadState from "../../components/admin/LoadState";
import StatTile from "../../components/admin/StatTile";
import { Chip } from "../../components/admin/StatusChip";
import { useAdminProperty } from "../../hooks/useAdminProperty";
import { usePolling } from "../../hooks/usePolling";
import {
  errorMessage,
  getDbSummary,
  listOccupancy,
  listProperties,
  uploadOccupancy,
  type OccupancyRow,
  type OccupancyUploadReport,
} from "../../lib/adminApi";
import { EMPTY, formatDate, formatDateRange, formatMoney, formatNumber, formatPct } from "../../lib/adminFormat";

const EXPECTED_HEADER =
  "target_date,room_occupancy_pct,adr,revpar,hall_utilization_pct,is_peak_season,local_event_multiplier";

const COLUMNS: AdminColumn<OccupancyRow>[] = [
  { key: "date", header: "Date", render: (r) => <span className="whitespace-nowrap">{formatDate(r.target_date)}</span> },
  { key: "occ", header: "Occupancy", numeric: true, render: (r) => formatPct(r.room_occupancy_pct) },
  { key: "hall", header: "Hall use", numeric: true, render: (r) => formatPct(r.hall_utilization_pct) },
  { key: "adr", header: "ADR", numeric: true, render: (r) => formatMoney(r.adr) },
  { key: "revpar", header: "RevPAR", numeric: true, render: (r) => formatMoney(r.revpar) },
  {
    key: "peak",
    header: "Peak",
    render: (r) => (r.is_peak_season ? <Chip tone="amber">Peak</Chip> : <span className="admin-faint text-xs">No</span>),
  },
  {
    key: "event",
    header: "Event multiplier",
    numeric: true,
    render: (r) => (r.local_event_multiplier == null ? EMPTY : `×${formatNumber(r.local_event_multiplier, 2)}`),
  },
];

const DB_TABLE_LABELS: Record<string, string> = {
  rfp: "Requests",
  quotes: "Quotes",
  occupancy: "Occupancy days",
  spaces: "Spaces",
};

function isCsv(file: File): boolean {
  return /\.csv$/i.test(file.name) || file.type === "text/csv";
}

function ImportReport({ report }: { report: OccupancyUploadReport }) {
  return (
    <section className="admin-card p-4" aria-labelledby="oc-report" aria-live="polite">
      <h3 id="oc-report" className="admin-section-title mb-3">
        Import report
      </h3>
      <div className="grid grid-cols-3 gap-3">
        <StatTile label="Added" value={report.created} tone={report.created ? "good" : "default"} />
        <StatTile label="Updated" value={report.updated} />
        <StatTile label="Skipped" value={report.skipped} tone={report.skipped ? "warn" : "default"} />
      </div>
      {report.errors?.length ? (
        <div className="mt-3">
          <p className="admin-muted mb-2 text-xs">These rows were skipped. Fix them in the file and upload it again.</p>
          <AdminTable
            caption="Rows that were skipped"
            columns={[
              { key: "row", header: "Row", numeric: true, render: (e) => e.row },
              { key: "error", header: "Problem", render: (e) => e.error },
            ]}
            rows={report.errors}
            rowKey={(e) => `${e.row}-${e.error}`}
            empty="No problems."
            maxHeight="14rem"
          />
        </div>
      ) : (
        <p className="admin-success-text mt-3 text-xs">Every row was imported.</p>
      )}
    </section>
  );
}

export default function OccupancyPage() {
  const { notify } = useAdminFeedback();
  const propsQ = usePolling(listProperties, 0);
  const [propertyId, setPropertyId] = useAdminProperty(propsQ.data);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const rangeInvalid = !!from && !!to && to < from;

  const rowsQ = usePolling(
    () =>
      propertyId
        ? listOccupancy({ property: propertyId, from: from || undefined, to: rangeInvalid ? undefined : to || undefined })
        : Promise.resolve([] as OccupancyRow[]),
    0,
    [propertyId, from, to, rangeInvalid],
  );
  const dbQ = usePolling(getDbSummary, 0);

  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [report, setReport] = useState<OccupancyUploadReport | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const pickFile = (f: File | null | undefined) => {
    setReport(null);
    if (!f) return;
    if (!isCsv(f)) {
      setFile(null);
      setFileError("That isn't a CSV file. Export your sheet as .csv and try again.");
      return;
    }
    setFileError(null);
    setFile(f);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  };

  const upload = async () => {
    if (!file || !propertyId) return;
    setUploading(true);
    try {
      const res = await uploadOccupancy(file, propertyId);
      setReport(res);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      notify(
        `Imported: ${res.created} added, ${res.updated} updated, ${res.skipped} skipped.`,
        res.skipped ? "warning" : "success",
      );
      await Promise.all([rowsQ.reload(), dbQ.reload()]);
    } catch (err) {
      const msg = errorMessage(err, "We couldn't import that file.");
      setFileError(msg);
      notify(msg, "error");
    } finally {
      setUploading(false);
    }
  };

  const copyHeader = async () => {
    try {
      await navigator.clipboard.writeText(EXPECTED_HEADER);
      notify("Header copied.", "success");
    } catch {
      notify("Couldn't copy automatically. Select the text and copy it instead.", "warning");
    }
  };

  const properties = propsQ.data ?? [];
  const db = dbQ.data;

  return (
    <AdminPanel
      kicker="Module 6 · Occupancy"
      title="Occupancy data"
      subtitle="Import daily occupancy so the pricing model can learn from demand."
      actions={
        <button
          type="button"
          className="studio-btn-secondary"
          onClick={() => {
            void propsQ.reload();
            void rowsQ.reload();
            void dbQ.reload();
          }}
        >
          <IconRefresh />
          Refresh
        </button>
      }
    >
      <div className="space-y-5">
        {!propsQ.data ? (
          <LoadState
            loading={propsQ.loading}
            error={propsQ.error}
            onRetry={() => void propsQ.reload()}
            errorTitle="We couldn't load your properties."
            compact
          />
        ) : properties.length === 0 ? (
          <div className="studio-empty-list">
            No properties yet. Add one on the{" "}
            <Link to="/admin/inventory" className="admin-link">
              Inventory page
            </Link>{" "}
            first, then import its occupancy here.
          </div>
        ) : (
          <>
            <label className="block max-w-sm">
              <span className="admin-label">Property</span>
              <select className="studio-field" value={propertyId ?? ""} onChange={(e) => setPropertyId(e.target.value)}>
                {properties.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>

            <section className="admin-card p-4" aria-labelledby="oc-upload">
              <h3 id="oc-upload" className="admin-section-title mb-3">
                Import a CSV
              </h3>
              <div
                className={`admin-dropzone flex flex-col items-center gap-2 px-4 py-6 text-center ${dragging ? "is-active" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
              >
                <span className="admin-muted" aria-hidden>
                  <IconUpload size={22} />
                </span>
                <p className="admin-fg text-sm">
                  {file ? (
                    <>
                      Ready to import <strong className="break-all">{file.name}</strong>
                    </>
                  ) : (
                    "Drop a CSV file here, or choose one"
                  )}
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  <input
                    ref={inputRef}
                    id="oc-file"
                    type="file"
                    accept=".csv,text/csv"
                    className="admin-sr-only peer"
                    onChange={(e) => pickFile(e.target.files?.[0])}
                  />
                  <label
                    htmlFor="oc-file"
                    className="studio-btn-secondary cursor-pointer peer-focus-visible:ring-2 peer-focus-visible:ring-violet-500/70"
                  >
                    Choose file
                  </label>
                  <button
                    type="button"
                    className="studio-btn-secondary admin-btn-primary"
                    disabled={!file || !propertyId || uploading}
                    onClick={() => void upload()}
                  >
                    <IconUpload size={14} />
                    {uploading ? "Uploading…" : "Upload CSV"}
                  </button>
                </div>
              </div>
              {fileError ? (
                <p className="admin-alert mt-3" role="alert">
                  {fileError}
                </p>
              ) : null}
              <div className="mt-3">
                <p className="admin-muted text-xs">
                  First row must be this header. The first four columns are required; rows with the same date are
                  updated.
                </p>
                <div className="mt-1.5 flex min-w-0 items-center gap-2">
                  <code className="admin-code studio-scroll block min-w-0 flex-1 select-all overflow-x-auto whitespace-nowrap py-1.5">
                    {EXPECTED_HEADER}
                  </code>
                  <button
                    type="button"
                    className="studio-btn-secondary admin-btn-small"
                    onClick={() => void copyHeader()}
                  >
                    <IconCopy />
                    Copy header
                  </button>
                </div>
              </div>
            </section>

            {report ? <ImportReport report={report} /> : null}

            <section className="admin-card min-w-0 p-4" aria-labelledby="oc-rows">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
                <h3 id="oc-rows" className="admin-section-title">
                  Daily occupancy
                </h3>
                <div className="flex flex-wrap items-end gap-2">
                  <label className="block">
                    <span className="admin-label">From</span>
                    <input type="date" className="studio-field !py-2" value={from} onChange={(e) => setFrom(e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="admin-label">To</span>
                    <input type="date" className="studio-field !py-2" value={to} onChange={(e) => setTo(e.target.value)} />
                  </label>
                  {from || to ? (
                    <button
                      type="button"
                      className="studio-btn-secondary admin-btn-small"
                      onClick={() => {
                        setFrom("");
                        setTo("");
                      }}
                    >
                      Clear dates
                    </button>
                  ) : null}
                </div>
              </div>
              {rangeInvalid ? (
                <p className="admin-alert admin-alert--warning mb-3">The end date is before the start date.</p>
              ) : null}
              <AdminTable
                caption="Daily occupancy"
                columns={COLUMNS}
                rows={rowsQ.data}
                rowKey={(r) => String(r.id ?? r.target_date)}
                loading={rowsQ.loading}
                error={rowsQ.error}
                onRetry={() => void rowsQ.reload()}
                errorTitle="We couldn't load occupancy."
                empty={
                  from || to
                    ? "No days in this date range. Try a wider range."
                    : "No occupancy data yet. Upload a CSV above to get started."
                }
                maxHeight="28rem"
              />
              {rowsQ.data && rowsQ.data.length >= 366 ? (
                <p className="admin-faint mt-2 text-xs">Showing the first 366 days. Use the dates to narrow it down.</p>
              ) : null}
            </section>
          </>
        )}

        <section className="admin-card p-4" aria-labelledby="oc-db">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 id="oc-db" className="admin-section-title">
              Database
            </h3>
            <Link to="/admin/pricing" className="studio-btn-secondary admin-btn-small">
              Retrain model
            </Link>
          </div>
          {!db ? (
            <LoadState
              loading={dbQ.loading}
              error={dbQ.error}
              onRetry={() => void dbQ.reload()}
              errorTitle="We couldn't load the database summary."
              compact
            />
          ) : (
            <div className="space-y-3">
              <p className="admin-muted text-xs">
                Running on <span className="admin-fg font-medium">{db.engine === "azuresql" ? "Azure SQL" : db.engine === "sqlite" ? "SQLite" : db.engine}</span>
                {db.vendor && db.vendor !== db.engine ? ` (${db.vendor})` : ""}. Data lives in this one database; there is no
                second copy to sync.
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Object.entries(db.tables ?? {}).map(([k, v]) => (
                  <StatTile key={k} label={DB_TABLE_LABELS[k] ?? k} value={v} />
                ))}
              </div>
              <p className="admin-faint text-xs">
                Occupancy covers {formatDateRange(db.occupancy_range?.from, db.occupancy_range?.to)}
              </p>
            </div>
          )}
        </section>
      </div>
    </AdminPanel>
  );
}
