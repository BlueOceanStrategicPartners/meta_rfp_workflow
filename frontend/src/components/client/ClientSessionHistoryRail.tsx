import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import CustomScrollArea, { type ScrollEdgeState } from "../ui/CustomScrollArea";
import ClientSessionProposalPreview from "./ClientSessionProposalPreview";
import type { ClientRfpSessionSummary } from "../../lib/clientApi";

type Props = {
  sessions: ClientRfpSessionSummary[];
  activeSessionId: string | null;
  loading?: boolean;
  composerOpen?: boolean;
  onSelect: (sessionId: string) => void;
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

export default function ClientSessionHistoryRail({
  sessions,
  activeSessionId,
  loading,
  composerOpen = false,
  onSelect,
}: Props) {
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
      <div className="client-side-deck__header client-session-rail__header flex shrink-0 items-center justify-between gap-2 px-2 pb-1">
        <h2 className="client-side-deck__title text-sm font-semibold tracking-tight">Your sessions</h2>
        {loading ? <span className="client-hint-muted text-[10px]">Syncing…</span> : null}
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
        >
          {sessions.length === 0 && !loading ? (
            <p className="client-hint-muted px-2 py-4 text-xs leading-relaxed">
              Start a new RFP with voice or the composer. Your sessions will appear here.
            </p>
          ) : null}
          {sessions.map((session) => {
            const active = session.id === activeSessionId;
            const card = session.proposal_card;
            return (
              <button
                key={session.id}
                type="button"
                onClick={() => onSelect(session.id)}
                className={[
                  "client-side-card client-session-card w-full text-left px-3 py-2.5 transition overflow-hidden",
                  active ? "client-session-card--active ring-1 ring-cyan-400/40" : "client-session-card--idle",
                ].join(" ")}
              >
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
            );
          })}
        </CustomScrollArea>
      </div>
    </motion.aside>
  );
}
