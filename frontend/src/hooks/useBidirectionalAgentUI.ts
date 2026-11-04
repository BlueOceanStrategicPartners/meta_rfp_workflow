import { useCallback, useEffect, useRef, useState } from "react";
import { cardsHaveIdentifiedFields } from "../lib/rfpFlow";
import type { ClientSessionState } from "../lib/clientSession";
import type { CardSaveState } from "./useDebouncedCardPatch";

export type AgentMessage = { type: string; payload?: Record<string, unknown> };

export function useBidirectionalAgentUI(
  sessionId: string | null,
  onAgentUtterance?: (text: string, options?: { mandatory?: boolean }) => void,
) {
  const [cards, setCards] = useState<Record<string, unknown>>({});
  const [clientSession, setClientSession] = useState<ClientSessionState>({});
  const [cardSaveState, setCardSaveState] = useState<CardSaveState>("idle");
  const [cardValidationError, setCardValidationError] = useState<string | null>(null);
  const [proposalHtml, setProposalHtml] = useState<string | null>(null);
  const [debateRings, setDebateRings] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const onUtteranceRef = useRef(onAgentUtterance);
  onUtteranceRef.current = onAgentUtterance;
  const saveResetTimer = useRef<number | null>(null);

  const markCardSaving = useCallback(() => {
    setCardSaveState("saving");
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/ws/rfp/${sessionId}/`;
    // Reconnect if the socket drops (backend restart, network blip); otherwise pushed messages
    // such as an admin's takeover replies would silently stop arriving.
    let stopped = false;
    let attempt = 0;
    let retryTimer: number | undefined;

    const onMessage = (ev: MessageEvent) => {
      const msg: AgentMessage = JSON.parse(ev.data);
      if (msg.type === "session_snapshot") {
        const payload = msg.payload || {};
        const next = (payload.cards as Record<string, unknown>) || {};
        if (cardsHaveIdentifiedFields(next)) {
          setCards(next);
        }
        const session = payload.client_session as ClientSessionState | undefined;
        if (session) setClientSession(session);
      }
      if (msg.type === "cards_patch") {
        const next = (msg.payload?.cards as Record<string, unknown>) || {};
        if (cardsHaveIdentifiedFields(next)) {
          setCards(next);
        } else if (Object.keys(next).length) {
          setCards((prev) => (cardsHaveIdentifiedFields(prev) ? prev : next));
        }
        setCardValidationError(null);
        setCardSaveState("saved");
        if (saveResetTimer.current) window.clearTimeout(saveResetTimer.current);
        saveResetTimer.current = window.setTimeout(() => setCardSaveState("idle"), 2200);
      }
      if (msg.type === "client_session_patch") {
        const session = (msg.payload?.session as ClientSessionState) || {};
        setClientSession(session);
      }
      if (msg.type === "proposal_html") {
        setProposalHtml(String(msg.payload?.html || ""));
      }
      if (msg.type === "debate_progress") {
        setDebateRings((r) => Math.min(3, r + 1));
      }
      if (msg.type === "validation_error") {
        setCardValidationError(String(msg.payload?.error || "Validation failed"));
        setCardSaveState("error");
      }
      if (msg.type === "agent_utterance") {
        const text = String(msg.payload?.text || "");
        if (text) onUtteranceRef.current?.(text, { mandatory: true });
      }
    };

    const connect = () => {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => {
        attempt = 0;
      };
      ws.onmessage = onMessage;
      ws.onclose = () => {
        if (stopped) return;
        const delay = Math.min(10_000, 1_000 * 2 ** attempt);
        attempt += 1;
        retryTimer = window.setTimeout(connect, delay);
      };
    };
    connect();

    return () => {
      stopped = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      wsRef.current?.close();
      if (saveResetTimer.current) window.clearTimeout(saveResetTimer.current);
    };
  }, [sessionId]);

  const submitCardMutation = useCallback(
    (payload: Record<string, unknown>) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setCardSaveState("error");
        setError("Connection lost — refresh and try again.");
        return;
      }
      setError(null);
      setCardValidationError(null);
      wsRef.current.send(JSON.stringify({ type: "card_mutation_submit", payload }));
    },
    [],
  );

  const hydrateSession = useCallback((payload: Record<string, unknown>) => {
    if (payload.active_ui_cards_json) {
      setCards(payload.active_ui_cards_json as Record<string, unknown>);
    }
  }, []);

  const clearProposalHtml = useCallback(() => setProposalHtml(null), []);

  return {
    cards,
    clientSession,
    cardSaveState,
    cardValidationError,
    proposalHtml,
    debateRings,
    error,
    submitCardMutation,
    markCardSaving,
    setCards,
    hydrateSession,
    clearProposalHtml,
    setProposalHtml,
  };
}

export function useDebateObservatory() {
  const [debates, setDebates] = useState<unknown[]>([]);
  useEffect(() => {
    fetch("/api/admin-center/debate-observatory/", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setDebates(d.debates || []))
      .catch(() => setDebates([]));
  }, []);
  return { debates };
}
