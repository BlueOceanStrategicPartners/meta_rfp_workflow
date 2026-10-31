import { useCallback, useEffect, useRef, useState } from "react";
import { cardsHaveExtraction } from "../lib/rfpFlow";

export type AgentMessage = { type: string; payload?: Record<string, unknown> };

export function useBidirectionalAgentUI(
  sessionId: string | null,
  onAgentUtterance?: (text: string, options?: { mandatory?: boolean }) => void,
) {
  const [cards, setCards] = useState<Record<string, unknown>>({});
  const [mapHighlights, setMapHighlights] = useState<string[]>([]);
  const [proposalHtml, setProposalHtml] = useState<string | null>(null);
  const [debateRings, setDebateRings] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const onUtteranceRef = useRef(onAgentUtterance);
  onUtteranceRef.current = onAgentUtterance;

  useEffect(() => {
    if (!sessionId) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/rfp/${sessionId}/`);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const msg: AgentMessage = JSON.parse(ev.data);
      if (msg.type === "session_snapshot") {
        const payload = msg.payload || {};
        const next = (payload.cards as Record<string, unknown>) || {};
        if (cardsHaveExtraction(next)) {
          setCards(next);
        }
      }
      if (msg.type === "cards_patch") {
        const next = (msg.payload?.cards as Record<string, unknown>) || {};
        if (cardsHaveExtraction(next) || Object.keys(next).length) {
          setCards(next);
        }
      }
      if (msg.type === "map_highlight") {
        setMapHighlights((msg.payload?.zone_ids as string[]) || []);
      }
      if (msg.type === "proposal_html") {
        setProposalHtml(String(msg.payload?.html || ""));
      }
      if (msg.type === "debate_progress") {
        setDebateRings((r) => Math.min(3, r + 1));
      }
      if (msg.type === "validation_error") {
        setError(String(msg.payload?.error || "Validation failed"));
      }
      if (msg.type === "agent_utterance") {
        const text = String(msg.payload?.text || "");
        if (text) onUtteranceRef.current?.(text, { mandatory: true });
      }
    };
    return () => ws.close();
  }, [sessionId]);

  const submitCardMutation = useCallback(
    (payload: Record<string, unknown>) => {
      wsRef.current?.send(JSON.stringify({ type: "card_mutation_submit", payload }));
    },
    [],
  );

  const hydrateSession = useCallback((payload: Record<string, unknown>) => {
    if (payload.active_ui_cards_json) {
      setCards(payload.active_ui_cards_json as Record<string, unknown>);
    }
  }, []);

  return {
    cards,
    mapHighlights,
    proposalHtml,
    debateRings,
    error,
    submitCardMutation,
    setCards,
    hydrateSession,
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
