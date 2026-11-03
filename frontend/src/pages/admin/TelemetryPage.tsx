import { useNavigate } from "react-router-dom";
import AdminPanel from "../../components/admin/AdminPanel";
import AdminTable, { type AdminColumn } from "../../components/admin/AdminTable";
import { IconRefresh } from "../../components/admin/AdminIcons";
import LoadState from "../../components/admin/LoadState";
import StatTile from "../../components/admin/StatTile";
import StatusChip from "../../components/admin/StatusChip";
import StatusFunnel from "../../components/admin/StatusFunnel";
import { usePolling } from "../../hooks/usePolling";
import { errorMessage, getTelemetry, type TelemetryData } from "../../lib/adminApi";
import {
  EMPTY,
  formatDateTime,
  formatDuration,
  formatMs,
  formatNumber,
  formatPct,
  formatRelativeTime,
  shortId,
} from "../../lib/adminFormat";

type SlaRow = TelemetryData["sla"]["recent"][number];

function slaColumns(target: number): AdminColumn<SlaRow>[] {
  return [
    { key: "id", header: "Request", render: (r) => <span className="admin-code">{shortId(r.rfp_id)}</span> },
    {
      key: "company",
      header: "Company",
      render: (r) => <span className="block max-w-[14rem] truncate">{r.company_name || "Unnamed"}</span>,
    },
    { key: "status", header: "Status", render: (r) => <StatusChip status={r.status} /> },
    {
      key: "duration",
      header: "Time to answer",
      numeric: true,
      render: (r) => {
        if (r.duration_seconds == null) return <span className="admin-faint">Still running</span>;
        const over = r.duration_seconds > target;
        return (
          <span className={over ? "admin-danger-text font-semibold" : ""}>
            {formatDuration(r.duration_seconds)}
            {over ? " · Over" : ""}
          </span>
        );
      },
    },
    {
      key: "started",
      header: "Started",
      render: (r) => (
        <time className="admin-muted whitespace-nowrap text-xs" dateTime={r.started_at ?? undefined} title={formatDateTime(r.started_at)}>
          {formatRelativeTime(r.started_at)}
        </time>
      ),
    },
  ];
}

export default function TelemetryPage() {
  const navigate = useNavigate();
  const { data, error, loading, refreshing, reload } = usePolling(getTelemetry, 0);

  const target = data?.sla.target_seconds ?? 120;
  const hasSla = !!data && data.sla.p50_seconds !== null && data.sla.p50_seconds !== undefined;
  const noneYet = "No completed requests yet";

  return (
    <AdminPanel
      kicker="Module 7 · Telemetry"
      title="Speed and conversion"
      subtitle={`How fast clients get an answer (goal: under ${target} seconds) and how many requests turn into bookings.`}
      actions={
        <button type="button" className="studio-btn-secondary" onClick={() => void reload()} disabled={refreshing}>
          <IconRefresh />
          Refresh
        </button>
      }
    >
      {!data ? (
        <LoadState loading={loading} error={error} onRetry={() => void reload()} errorTitle="We couldn't load telemetry." />
      ) : (
        <div className="space-y-5">
          {error ? (
            <div className="admin-alert admin-alert--warning" role="status">
              Couldn't refresh, showing the last data we had. {errorMessage(error)}
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <StatTile
              label="Typical time to answer"
              value={hasSla ? formatDuration(data.sla.p50_seconds) : EMPTY}
              sub={hasSla ? "Median (p50)" : noneYet}
              tone={hasSla && (data.sla.p50_seconds ?? 0) > target ? "bad" : "default"}
            />
            <StatTile
              label="Slowest 5%"
              value={hasSla ? formatDuration(data.sla.p95_seconds) : EMPTY}
              sub={hasSla ? "p95" : noneYet}
              tone={hasSla && (data.sla.p95_seconds ?? 0) > target ? "bad" : "default"}
            />
            <StatTile
              label={`Within ${target} s`}
              value={hasSla ? formatPct(data.sla.within_target_pct) : EMPTY}
              sub={hasSla ? "Share of answered requests" : noneYet}
              tone={
                hasSla && data.sla.within_target_pct !== null
                  ? data.sla.within_target_pct >= 0.9
                    ? "good"
                    : "warn"
                  : "default"
              }
            />
            <StatTile
              label="Booked"
              value={formatPct(data.conversion.rate)}
              sub={`${data.conversion.booked} of ${data.conversion.total} requests`}
            />
          </div>

          <section className="admin-card min-w-0 p-4" aria-labelledby="tm-sla">
            <h3 id="tm-sla" className="admin-section-title mb-3">
              Recent requests
            </h3>
            <AdminTable
              caption="Response time for recent requests"
              columns={slaColumns(target)}
              rows={data.sla.recent ?? []}
              rowKey={(r) => r.rfp_id}
              onRowClick={(r) => navigate(`/admin/debates/${encodeURIComponent(r.rfp_id)}`)}
              rowLabel={(r) => `Open ${r.company_name || "request"}`}
              empty="No requests yet. Response times show up here once clients submit requests."
              maxHeight="24rem"
            />
          </section>

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="admin-card p-4" aria-labelledby="tm-funnel">
              <h3 id="tm-funnel" className="admin-section-title mb-3">
                Where requests are
              </h3>
              {data.funnel?.length ? (
                <StatusFunnel counts={data.funnel} />
              ) : (
                <div className="studio-empty-list">No requests yet.</div>
              )}
            </section>

            <section className="admin-card p-4" aria-labelledby="tm-debate">
              <h3 id="tm-debate" className="admin-section-title mb-3">
                Agent checks
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <StatTile label="Avg rounds" value={formatNumber(data.debate.avg_rounds, 1)} sub="Per request" />
                <StatTile label="Avg agreement" value={formatPct(data.debate.avg_consensus)} sub="Between the agents" />
                <StatTile
                  label="Left with fields to check"
                  value={formatPct(data.debate.partial_rate)}
                  sub="Needed a human look"
                  tone={(data.debate.partial_rate ?? 0) > 0.25 ? "warn" : "default"}
                />
                <StatTile label="Avg check time" value={formatMs(data.debate.avg_critic_ms)} sub="Per round" />
              </div>
            </section>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="admin-card p-4" aria-labelledby="tm-pricing">
              <h3 id="tm-pricing" className="admin-section-title mb-3">
                Pricing
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <StatTile label="Quotes" value={data.pricing.quotes} />
                <StatTile
                  label="Fallback pricing"
                  value={formatPct(data.pricing.fallback_rate)}
                  sub="Quotes made without the model"
                />
              </div>
            </section>

            <section className="admin-card p-4" aria-labelledby="tm-tokens">
              <h3 id="tm-tokens" className="admin-section-title mb-3">
                Token usage
              </h3>
              {data.tokens == null ? (
                <div className="studio-empty-list">
                  <p className="admin-fg text-sm font-medium">Not recorded yet</p>
                  <p className="mt-1">Token counts will appear here once model call logging is added.</p>
                </div>
              ) : (
                <pre className="admin-pre studio-scroll max-h-48 overflow-auto">{JSON.stringify(data.tokens, null, 2)}</pre>
              )}
            </section>
          </div>
        </div>
      )}
    </AdminPanel>
  );
}
