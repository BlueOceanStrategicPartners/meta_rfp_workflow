import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AdminPanel from "../../components/admin/AdminPanel";
import AdminTable, { type AdminColumn } from "../../components/admin/AdminTable";
import { IconRefresh } from "../../components/admin/AdminIcons";
import { useAnnounceError } from "../../components/admin/AdminLayout";
import { RefreshingDot } from "../../components/admin/LoadState";
import StatusChip, { Chip } from "../../components/admin/StatusChip";
import { usePolling } from "../../hooks/usePolling";
import { listRfps, type RfpListItem } from "../../lib/adminApi";
import { RFP_STATUSES, formatDateTime, formatPct, formatRelativeTime, shortId, statusMeta } from "../../lib/adminFormat";

const COLUMNS: AdminColumn<RfpListItem>[] = [
  {
    key: "id",
    header: "Request",
    render: (r) => <span className="admin-code">{shortId(r.id)}</span>,
  },
  {
    key: "company",
    header: "Company",
    render: (r) => (
      <span className="block max-w-[16rem] truncate font-medium">{r.company_name || "Not found yet"}</span>
    ),
  },
  { key: "status", header: "Status", render: (r) => <StatusChip status={r.status} /> },
  { key: "rounds", header: "Rounds", numeric: true, render: (r) => r.rounds ?? 0 },
  { key: "consensus", header: "Agreement", numeric: true, render: (r) => formatPct(r.latest_consensus) },
  {
    key: "amber",
    header: "To check",
    render: (r) =>
      r.amber_fields?.length ? (
        <Chip tone="amber">
          {r.amber_fields.length} {r.amber_fields.length === 1 ? "field" : "fields"}
        </Chip>
      ) : (
        <span className="admin-faint text-xs">None</span>
      ),
  },
  {
    key: "updated",
    header: "Updated",
    render: (r) => (
      <time className="admin-muted whitespace-nowrap text-xs" dateTime={r.updated_at} title={formatDateTime(r.updated_at)}>
        {formatRelativeTime(r.updated_at)}
      </time>
    ),
  },
];

export default function DebatesPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");

  // Debounce typing so we don't refetch on every key.
  useEffect(() => {
    const id = window.setTimeout(() => setQ(search.trim()), 300);
    return () => window.clearTimeout(id);
  }, [search]);

  const { data, error, loading, refreshing, reload } = usePolling(
    () => listRfps({ status: status || undefined, q: q || undefined }),
    10_000,
    [status, q],
  );
  useAnnounceError(error, "Couldn't refresh the request list.");

  const filtered = !!status || !!q;

  return (
    <AdminPanel
      kicker="Module 2 · Debates"
      title="Requests and agent checks"
      subtitle="Every request, how the agents read it, and what still needs a human check."
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
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
          <label className="block min-w-0">
            <span className="admin-label">Status</span>
            <select className="studio-field" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {RFP_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {statusMeta(s).step}
                </option>
              ))}
            </select>
          </label>
          <label className="block min-w-0">
            <span className="admin-label">Search</span>
            <input
              type="search"
              className="studio-field"
              placeholder="Company name or request ID"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
        </div>

        <AdminTable
          caption="Requests"
          columns={COLUMNS}
          rows={data}
          rowKey={(r) => r.id}
          onRowClick={(r) => navigate(`/admin/debates/${encodeURIComponent(r.id)}`)}
          rowLabel={(r) => `Open ${r.company_name || "request"} ${shortId(r.id)}`}
          rowClassName={(r) => (r.amber_fields?.length ? "admin-amber-outline" : "")}
          loading={loading}
          error={error}
          onRetry={() => void reload()}
          errorTitle="We couldn't load the requests."
          empty={
            filtered
              ? "No requests match these filters. Try another status or clear the search."
              : "No requests yet. Submit one from the Client page and it will show up here."
          }
        />
        {data && data.length >= 100 ? (
          <p className="admin-faint text-xs">Showing the newest 100. Use search to find older requests.</p>
        ) : null}
      </div>
    </AdminPanel>
  );
}
