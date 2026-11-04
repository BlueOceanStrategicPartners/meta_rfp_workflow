import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import CustomScrollArea, { type ScrollEdgeState } from "../ui/CustomScrollArea";
import ClientSessionProposalPreview from "./ClientSessionProposalPreview";
import type { ClientRfpSessionSummary } from "../../lib/clientApi";

type Props = {
  sessions: ClientRfpSessionSummary[];
  activeSessionId: string | null;
  loading?: boolean;
  composerOpen?: boolean;
  archiveBusyId?: string | null;
  onSelect: (sessionId: string) => void;
  onArchive: (sessionId: string, archived: boolean) => boolean | null | Promise<boolean | null>;
};

function formatEstimate(value: unknown) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function formatWhen(iso: string) {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(
      new Date(iso),
    );
  } catch {
    return iso.slice(0, 10);
  }
}

function IconArchive() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 14h10l1-14"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 11v6M14 11v6" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

const CARD_EASE: [number, number, number, number] = [0.45, 0.05, 0.25, 1];

const sessionCardMotion = {
  exit: {
    opacity: 0,
    x: -36,
    scale: 0.88,
    filter: "blur(3px)",
    height: 0,
    marginBottom: 0,
    overflow: "hidden",
    transition: { duration: 0.38, ease: CARD_EASE },
  },
};

export default function ClientSessionHistoryRail({
  sessions,
  activeSessionId,
  loading,
  composerOpen = false,
  archiveBusyId = null,
  onSelect,
  onArchive,
}: Props) {
  const [showArchived, setShowArchived] = useState(false);
  const [scrollEdges, setScrollEdges] = useState<ScrollEdgeState>({
    canScroll: false,
    atTop: true,
    atBottom: true,
  });
  const onScrollEdges = useCallback((state: ScrollEdgeState) => {
    setScrollEdges((prev) =>
      prev.canScroll === state.canScroll && prev.atTop === state.atTop && prev.atBottom === state.atBottom
        ? prev
        : state,
    );
  }, []);

  const visibleSessions = useMemo(
    () => sessions.filter((s) => Boolean(s.archived) === showArchived),
    [sessions, showArchived],
  );

  const archivedCount = useMemo(() => sessions.filter((s) => s.archived).length, [sessions]);

  const listKey = showArchived ? "archived" : "active";

  useEffect(() => {
    setScrollEdges({ canScroll: false, atTop: true, atBottom: true });
  }, [listKey]);

  const showTopFade = scrollEdges.canScroll && !scrollEdges.atTop;
  const showBottomFade = scrollEdges.canScroll && !scrollEdges.atBottom;

  return (
    <motion.aside
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, ease: [0.45, 0.05, 0.25, 1] }}
      className={[
        "client-side-deck client-session-rail pointer-events-auto fixed left-3 top-[4.75rem] z-30 flex w-[min(20rem,calc(100vw-1.5rem))] flex-col sm:left-4 sm:w-80",
        composerOpen ? "bottom-[7.25rem]" : "bottom-14",
      ].join(" ")}
      aria-label="Your RFP sessions"
    >
      <div className="client-side-deck__header client-session-rail__header flex shrink-0 flex-col gap-2 px-2 pb-1">
        <div className="flex items-center justify-between gap-2">
          <h2 className="client-side-deck__title text-sm font-semibold tracking-tight">Your sessions</h2>
          {loading ? <span className="client-hint-muted text-[10px]">Syncing…</span> : null}
        </div>
        <div className="client-session-rail__filter" role="group" aria-label="Show sessions">
          <button
            type="button"
            className={["client-session-rail__filter-btn", !showArchived ? "client-session-rail__filter-btn--active" : ""].join(
              " ",
            )}
            aria-pressed={!showArchived}
            onClick={() => setShowArchived(false)}
          >
            Active
          </button>
          <button
            type="button"
            className={["client-session-rail__filter-btn", showArchived ? "client-session-rail__filter-btn--active" : ""].join(
              " ",
            )}
            aria-pressed={showArchived}
            onClick={() => setShowArchived(true)}
          >
            Archived{archivedCount > 0 ? ` (${archivedCount})` : ""}
          </button>
        </div>
      </div>

      <div className="client-side-deck-scroll-shell client-session-rail__scroll relative min-h-0 flex-1">
        <div
          className={[
            "client-side-deck-scroll-fade client-side-deck-scroll-fade--top",
            showTopFade ? "client-side-deck-scroll-fade--visible" : "",
          ].join(" ")}
          aria-hidden
        />
        <div
          className={[
            "client-side-deck-scroll-fade client-side-deck-scroll-fade--bottom",
            showBottomFade ? "client-side-deck-scroll-fade--visible" : "",
          ].join(" ")}
          aria-hidden
        />
        <CustomScrollArea
          className="absolute inset-0"
          contentClassName="client-session-rail__scroll-content flex flex-col gap-2.5"
          onScrollEdges={onScrollEdges}
          contentKey={listKey}
        >
          <div key={listKey} className="flex flex-col gap-2.5">
            <AnimatePresence mode="sync" initial={false}>
              {visibleSessions.map((session) => {
                const active = session.id === activeSessionId;
                const card = session.proposal_card;
                const archived = Boolean(session.archived);
                const archiveBusy = archiveBusyId === session.id;
                return (
                  <motion.div
                    key={session.id}
                    initial={false}
                    exit="exit"
                    variants={sessionCardMotion}
                    className={[
                      "client-side-card client-session-card w-full overflow-hidden px-3 py-2.5 transition",
                      active ? "client-session-card--active ring-1 ring-cyan-400/40" : "client-session-card--idle",
                      archived ? "client-session-card--archived" : "",
                      archiveBusy ? "client-session-card--archiving" : "",
                    ].join(" ")}
                  >
                  <button type="button" onClick={() => onSelect(session.id)} className="w-full text-left">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium leading-snug line-clamp-2">{session.title}</p>
                      {session.completed ? (
                        <span className="client-session-badge shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide">
                          Proposal
                        </span>
                      ) : (
                        <span className="client-session-badge client-session-badge--live shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide">
                          Active
                        </span>
                      )}
                    </div>
                    <p className="client-hint-muted mt-1 text-[10px]">{formatWhen(session.updated_at || session.created_at)}</p>
                    {session.completed && card ? (
                      <div className="client-session-proposal-block mt-2.5">
                        <div className="client-session-proposal-mini">
                          <ClientSessionProposalPreview
                            sessionId={session.id}
                            fallback={
                              <div className="client-session-proposal-mini__fallback px-2.5 py-2 text-[11px] leading-snug">
                                <p className="client-session-proposal-mini__title">{card.company_name || session.title}</p>
                                <p className="client-session-proposal-mini__dates client-hint-muted mt-0.5">
                                  {[card.check_in_date, card.check_out_date].filter(Boolean).join(" → ") || "Dates TBD"}
                                </p>
                              </div>
                            }
                          />
                        </div>
                        <div className="client-session-proposal-mini__footer text-[11px] leading-snug">
                          <p className="client-session-proposal-mini__dates client-hint-muted truncate">
                            {[card.check_in_date, card.check_out_date].filter(Boolean).join(" → ") || "Dates TBD"}
                          </p>
                          <p className="client-session-proposal-mini__quote mt-0.5 truncate">
                            {formatEstimate(card.estimate)}
                            {card.peak_rooms != null ? ` · ${card.peak_rooms} rooms` : ""}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <p className="client-hint-muted mt-2 text-xs leading-snug line-clamp-3">{session.last_snippet}</p>
                    )}
                  </button>
                  <div className="client-session-card__footer mt-1.5 flex items-center justify-end border-t border-white/[0.06] pt-1.5">
                    <button
                      type="button"
                      disabled={archiveBusy}
                      className="client-session-archive-btn"
                      title={archived ? "Restore to Active" : "Archive session"}
                      aria-label={archived ? "Restore session" : "Archive session"}
                      onPointerDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      void (async () => {
                        const nextArchived = !archived;
                        const result = await onArchive(session.id, nextArchived);
                        if (result === false) {
                          setShowArchived(false);
                        }
                      })();
                    }}
                    >
                      <IconArchive />
                      <span className="client-session-archive-btn__label">{archived ? "Restore" : "Archive"}</span>
                    </button>
                  </div>
                </motion.div>
              );
            })}
            </AnimatePresence>
            {visibleSessions.length === 0 && !loading ? (
              <p className="client-hint-muted px-2 py-4 text-xs leading-relaxed">
                {showArchived
                  ? "No archived sessions. Use Archive on a session card to hide it from Active."
                  : "Start a new RFP with voice or the composer. Your sessions will appear here."}
              </p>
            ) : null}
          </div>
        </CustomScrollArea>
      </div>
    </motion.aside>
  );
}
