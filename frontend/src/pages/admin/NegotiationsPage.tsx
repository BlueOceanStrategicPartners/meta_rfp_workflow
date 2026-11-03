import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import ActivityList from "../../components/admin/ActivityList";
import AdminConfirm from "../../components/admin/AdminConfirm";
import AdminPanel from "../../components/admin/AdminPanel";
import { IconHeadset, IconRefresh, IconSend } from "../../components/admin/AdminIcons";
import { useAdminFeedback, useAnnounceError } from "../../components/admin/AdminLayout";
import LoadState, { RefreshingDot } from "../../components/admin/LoadState";
import PriceLadder from "../../components/admin/PriceLadder";
import StatusChip, { Chip } from "../../components/admin/StatusChip";
import { usePolling } from "../../hooks/usePolling";
import {
  errorMessage,
  listAudit,
  listNegotiations,
  releaseNegotiation,
  sendNegotiationMessage,
  takeOverNegotiation,
  type NegotiationItem,
} from "../../lib/adminApi";
import {
  TAKEOVER_STATUSES,
  formatDateRange,
  formatMoney,
  formatRelativeTime,
  shortId,
} from "../../lib/adminFormat";

const MAX_MESSAGE = 500;

function isLive(n: NegotiationItem): boolean {
  return n.taken_over || n.status === "ESCALATED";
}

function NegotiationList({
  items,
  selectedId,
  onSelect,
}: {
  items: NegotiationItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <ul className="space-y-2" aria-label="Active negotiations">
      {items.map((n) => {
        const selected = n.id === selectedId;
        return (
          <li key={n.id}>
            <button
              type="button"
              onClick={() => onSelect(n.id)}
              aria-current={selected ? "true" : undefined}
              className={`admin-card block w-full px-3 py-2.5 text-left transition hover:bg-[color:var(--admin-hover)] ${
                selected ? "!border-violet-400/60 bg-[color:var(--admin-hover)]" : ""
              }`}
            >
              <span className="flex items-start justify-between gap-2">
                <span className="admin-fg min-w-0 truncate text-sm font-medium">{n.company_name || "Unnamed request"}</span>
                {isLive(n) ? (
                  <Chip tone="amber">You're live</Chip>
                ) : (
                  <StatusChip status={n.status} />
                )}
              </span>
              <span className="admin-faint mt-1 block text-xs">{formatDateRange(n.check_in_date, n.check_out_date)}</span>
              <span className="admin-muted admin-num mt-1 flex flex-wrap gap-x-3 text-xs">
                <span>Anchor {formatMoney(n.latest_quote?.anchor)}</span>
                <span>Agreed {formatMoney(n.latest_quote?.agreed)}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function NegotiationDetail({ item, onChanged }: { item: NegotiationItem; onChanged: () => Promise<void> }) {
  const { notify } = useAdminFeedback();
  const [confirm, setConfirm] = useState<"takeover" | "release" | null>(null);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const live = isLive(item);
  const canTakeOver = !live && TAKEOVER_STATUSES.includes(item.status);

  const activity = usePolling(
    () => listAudit({ target_type: "rfp", target_id: item.id, limit: 50 }),
    10_000,
    [item.id],
  );

  const runAction = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm === "takeover") {
        await takeOverNegotiation(item.id);
        notify("You're live. The client has been told a team member is joining.", "success");
      } else {
        await releaseNegotiation(item.id);
        notify("Handed back. The AI agent is replying again.", "success");
      }
      setConfirm(null);
      await Promise.all([onChanged(), activity.reload()]);
    } catch (err) {
      setConfirm(null);
      notify(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const trimmed = text.trim();
  const tooLong = trimmed.length > MAX_MESSAGE;
  const send = async () => {
    if (!trimmed || tooLong || !live) return;
    setSending(true);
    try {
      await sendNegotiationMessage(item.id, trimmed);
      setText("");
      notify("Sent. The client will hear it in the agent's voice.", "success");
      await activity.reload();
    } catch (err) {
      notify(errorMessage(err, "We couldn't send that message."), "error");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-w-0 space-y-4">
      <AdminConfirm
        open={confirm === "takeover"}
        title="Take over this conversation?"
        message="The AI agent stops replying and the client hears: “A member of our events team is joining the conversation now.”"
        confirmLabel="Take over"
        busyLabel="Taking over…"
        busy={busy}
        onConfirm={() => void runAction()}
        onCancel={() => setConfirm(null)}
      />
      <AdminConfirm
        open={confirm === "release"}
        title="Hand back to the AI agent?"
        message="The agent starts replying again and tells the client: “Thanks for waiting. I'll pick things up from here.”"
        confirmLabel="Hand back"
        busyLabel="Handing back…"
        busy={busy}
        onConfirm={() => void runAction()}
        onCancel={() => setConfirm(null)}
      />

      <section className="admin-card p-4" aria-labelledby="ng-summary">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 id="ng-summary" className="admin-fg truncate text-base font-semibold">
              {item.company_name || "Unnamed request"}
            </h3>
            <p className="admin-faint mt-0.5 text-xs">
              Request{" "}
              <Link to={`/admin/debates/${encodeURIComponent(item.id)}`} className="admin-link">
                {shortId(item.id)}
              </Link>{" "}
              · updated {formatRelativeTime(item.updated_at)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {live ? (
              <button type="button" className="studio-btn-secondary" disabled={busy} onClick={() => setConfirm("release")}>
                Hand back
              </button>
            ) : (
              <button
                type="button"
                className="studio-btn-secondary admin-btn-primary"
                disabled={!canTakeOver || busy}
                onClick={() => setConfirm("takeover")}
                title={canTakeOver ? undefined : "This request can't be taken over in its current state."}
              >
                <IconHeadset />
                Take over
              </button>
            )}
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <dt className="admin-label">Status</dt>
            <dd>{live ? <Chip tone="amber">You're live</Chip> : <StatusChip status={item.status} />}</dd>
          </div>
          <div>
            <dt className="admin-label">Dates</dt>
            <dd className="admin-fg text-sm">{formatDateRange(item.check_in_date, item.check_out_date)}</dd>
          </div>
          <div>
            <dt className="admin-label">Headcount</dt>
            <dd className="admin-fg admin-num text-sm">{item.headcount ?? "—"}</dd>
          </div>
          <div>
            <dt className="admin-label">Taken over by</dt>
            <dd className="admin-fg truncate text-sm">{live ? item.taken_over_by || "A team member" : "Nobody"}</dd>
          </div>
        </dl>

        <div className="mt-4">
          <p className="admin-label">Latest quote</p>
          {item.latest_quote ? (
            <PriceLadder
              floor={item.latest_quote.floor}
              target={item.latest_quote.target}
              anchor={item.latest_quote.anchor}
              agreed={item.latest_quote.agreed}
            />
          ) : (
            <div className="studio-empty-list">No quote yet for this request.</div>
          )}
        </div>
      </section>

      <section className="admin-card p-4" aria-labelledby="ng-message">
        <h3 id="ng-message" className="admin-section-title">
          Message the client
        </h3>
        <p className="admin-muted mb-3 mt-0.5 text-xs">
          {live
            ? "You're live. What you type is spoken to the client."
            : "Take over the conversation first to send your own messages."}
        </p>
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <label htmlFor="ng-text" className="admin-sr-only">
            Message to the client
          </label>
          <textarea
            id="ng-text"
            className={`studio-field min-h-[5.5rem] resize-y ${tooLong ? "admin-field-invalid" : ""}`}
            placeholder="Typed messages are spoken to the client in the agent's voice."
            value={text}
            disabled={!live || sending}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className={`admin-num text-[11px] ${tooLong ? "admin-danger-text" : "admin-faint"}`}>
              {trimmed.length} / {MAX_MESSAGE}
              {tooLong ? " · too long" : ""}
            </span>
            <button
              type="submit"
              className="studio-btn-secondary admin-btn-primary"
              disabled={!live || !trimmed || tooLong || sending}
            >
              <IconSend />
              {sending ? "Sending…" : "Send to client"}
            </button>
          </div>
        </form>
      </section>

      <section className="admin-card p-4" aria-labelledby="ng-activity">
        <h3 id="ng-activity" className="admin-section-title mb-1">
          Activity
        </h3>
        {activity.data ? (
          <ActivityList
            events={activity.data}
            empty="Nothing yet. Takeovers, hand-backs and your messages will be listed here."
          />
        ) : (
          <LoadState
            loading={activity.loading}
            error={activity.error}
            onRetry={() => void activity.reload()}
            errorTitle="We couldn't load the activity."
            compact
          />
        )}
      </section>
    </div>
  );
}

export default function NegotiationsPage() {
  const [params, setParams] = useSearchParams();
  const { data, error, loading, refreshing, reload } = usePolling(listNegotiations, 10_000);
  useAnnounceError(error, "Couldn't refresh negotiations.");

  const requested = params.get("rfp");
  const items = data ?? [];
  const selected = items.find((n) => n.id === requested) ?? (requested ? null : items[0] ?? null);

  const select = (id: string) => {
    const next = new URLSearchParams(params);
    next.set("rfp", id);
    setParams(next, { replace: true });
  };

  return (
    <AdminPanel
      kicker="Module 4 · Negotiations"
      title="Live negotiations"
      subtitle="Watch the agent negotiate, and step in yourself when a client needs a person."
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
        <LoadState loading={loading} error={error} onRetry={() => void reload()} errorTitle="We couldn't load negotiations." />
      ) : items.length === 0 ? (
        <div className="studio-empty-list">
          No live negotiations. When a client reaches pricing or starts negotiating, they'll show up here.
        </div>
      ) : (
        <div className="space-y-3">
          {error ? (
            <div className="admin-alert admin-alert--warning" role="status">
              Couldn't refresh, showing the last data we had. {errorMessage(error)}
            </div>
          ) : null}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,19rem)_minmax(0,1fr)]">
            <div className="studio-scroll max-h-[40vh] min-w-0 overflow-y-auto lg:max-h-none">
              <NegotiationList items={items} selectedId={selected?.id ?? null} onSelect={select} />
            </div>
            {selected ? (
              <NegotiationDetail key={selected.id} item={selected} onChanged={reload} />
            ) : (
              <div className="studio-empty-list">
                That negotiation isn't active any more. Pick one from the list.
              </div>
            )}
          </div>
        </div>
      )}
    </AdminPanel>
  );
}
