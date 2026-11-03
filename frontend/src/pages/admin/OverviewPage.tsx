import { Link } from "react-router-dom";
import ActivityList from "../../components/admin/ActivityList";
import AdminPanel from "../../components/admin/AdminPanel";
import { IconChevronRight, IconRefresh } from "../../components/admin/AdminIcons";
import { useAnnounceError } from "../../components/admin/AdminLayout";
import LoadState, { RefreshingDot } from "../../components/admin/LoadState";
import StatTile from "../../components/admin/StatTile";
import { Chip } from "../../components/admin/StatusChip";
import StatusFunnel from "../../components/admin/StatusFunnel";
import { usePolling } from "../../hooks/usePolling";
import { errorMessage, getOverview, type AttentionItem, type OverviewData } from "../../lib/adminApi";
import { EMPTY, formatDuration, formatPct, shortId } from "../../lib/adminFormat";

function attentionLink(item: AttentionItem): { to: string; label: string; tone: "amber" | "sky" } {
  if (item.reason === "escalated") {
    return {
      to: `/admin/negotiations?rfp=${encodeURIComponent(item.rfp_id)}`,
      label: "Human takeover",
      tone: "amber",
    };
  }
  return { to: `/admin/debates/${encodeURIComponent(item.rfp_id)}`, label: "Details to check", tone: "sky" };
}

function Tiles({ data }: { data: OverviewData }) {
  const booked = data.rfps.by_status?.BOOKED ?? 0;
  const active = Math.max(0, data.rfps.total - booked);
  const hasSla = (data.sla.measured ?? 0) > 0 && data.sla.p50_seconds !== null;
  const within = data.sla.within_target_pct;
  const target = data.sla.target_seconds ?? 120;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 2xl:grid-cols-6">
      <StatTile label="Active requests" value={active} sub={`${data.rfps.total} in total`} />
      <StatTile
        label="Typical response time"
        value={hasSla ? formatDuration(data.sla.p50_seconds) : EMPTY}
        sub={hasSla ? `Median · target ${target} s` : "No completed requests yet"}
        tone={hasSla && (data.sla.p50_seconds ?? 0) > target ? "bad" : "default"}
      />
      <StatTile
        label="Within 2 minutes"
        value={hasSla ? formatPct(within) : EMPTY}
        sub={hasSla ? `${data.sla.measured} measured` : "No completed requests yet"}
        tone={hasSla && within !== null ? (within >= 0.9 ? "good" : "warn") : "default"}
      />
      <StatTile
        label="Avg agreement"
        value={formatPct(data.debate.avg_consensus)}
        sub={`${data.debate.rounds} check rounds`}
      />
      <StatTile
        label="Fallback pricing"
        value={formatPct(data.pricing.fallback_rate)}
        sub={`${data.pricing.quotes} quotes · model ${data.pricing.model_trained ? "trained" : "not trained"}`}
      />
      <StatTile
        label="Spaces booked"
        value={`${data.inventory.booked} / ${data.inventory.spaces}`}
        sub={`${data.inventory.properties} ${data.inventory.properties === 1 ? "property" : "properties"}`}
      />
    </div>
  );
}

export default function OverviewPage() {
  const { data, error, loading, refreshing, reload } = usePolling(getOverview, 10_000);
  useAnnounceError(error, "Couldn't refresh the overview.");

  return (
    <AdminPanel
      kicker="Overview"
      title="Today at a glance"
      subtitle="Live requests, pricing and inventory. Updates every 10 seconds."
      actions={
        <>
          <RefreshingDot active={refreshing && !loading} />
          <button type="button" className="studio-btn-secondary" onClick={() => void reload()} disabled={refreshing}>
            <IconRefresh />
            Refresh
          </button>
        </>
      }
    >
      {!data ? (
        <LoadState loading={loading} error={error} onRetry={() => void reload()} errorTitle="We couldn't load the overview." />
      ) : (
        <div className="space-y-5">
          {error ? (
            <div className="admin-alert admin-alert--warning" role="status">
              Couldn't refresh, showing the last data we had. {errorMessage(error)}
            </div>
          ) : null}

          <Tiles data={data} />

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="admin-card p-4" aria-labelledby="ov-funnel">
              <h3 id="ov-funnel" className="admin-section-title mb-3">
                Where requests are
              </h3>
              {data.rfps.total === 0 ? (
                <div className="studio-empty-list">
                  No requests yet. Submit one from the Client page and it will show up here.
                </div>
              ) : (
                <StatusFunnel counts={data.rfps.by_status ?? {}} />
              )}
            </section>

            <section className="admin-card p-4" aria-labelledby="ov-attention">
              <h3 id="ov-attention" className="admin-section-title mb-3">
                Needs attention
              </h3>
              {data.attention.length === 0 ? (
                <div className="studio-empty-list">
                  Nothing needs you right now. Taken-over chats and requests with details to check will show up here.
                </div>
              ) : (
                <ul className="studio-scroll max-h-72 space-y-2 overflow-y-auto">
                  {data.attention.map((item) => {
                    const link = attentionLink(item);
                    return (
                      <li key={`${item.rfp_id}-${item.reason}`}>
                        <Link
                          to={link.to}
                          className="admin-card flex items-center justify-between gap-3 px-3 py-2.5 transition hover:bg-[color:var(--admin-hover)]"
                        >
                          <span className="min-w-0">
                            <span className="admin-fg block truncate text-sm font-medium">
                              {item.company_name || "Unnamed request"}
                            </span>
                            <span className="admin-faint block text-xs">Request {shortId(item.rfp_id)}</span>
                          </span>
                          <span className="flex shrink-0 items-center gap-2">
                            <Chip tone={link.tone}>{link.label}</Chip>
                            <span className="admin-faint" aria-hidden>
                              <IconChevronRight />
                            </span>
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>

          <section className="admin-card p-4" aria-labelledby="ov-activity">
            <h3 id="ov-activity" className="admin-section-title mb-1">
              Recent activity
            </h3>
            <ActivityList
              events={(data.recent_activity ?? []).slice(0, 10)}
              empty="No admin activity yet. Changes you make here, like saving the pricing policy, will be listed."
            />
          </section>
        </div>
      )}
    </AdminPanel>
  );
}
