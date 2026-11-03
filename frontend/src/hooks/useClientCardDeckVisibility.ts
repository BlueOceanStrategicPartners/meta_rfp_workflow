import { useMemo } from "react";
import type { AgentUiComponent } from "../lib/agentUiComponents";
import { cardsHaveIdentifiedFields } from "../lib/rfpFlow";

/**
 * Side RFP cards appear only after the agent or extraction has identified real event data.
 * Availability / other generative panels use the same side column when active.
 */
export function useClientCardDeckVisibility(
  sessionId: string | null,
  cards: Record<string, unknown>,
  agentUiComponent: AgentUiComponent | null,
) {
  return useMemo(() => {
    const identified = cardsHaveIdentifiedFields(cards);
    const showCardDeck = Boolean(sessionId && identified);
    const showGenerativeSidePanel = Boolean(agentUiComponent);
    return {
      identified,
      showCardDeck,
      showGenerativeSidePanel,
      dockSideForGenerative: showCardDeck ? ("left" as const) : ("right" as const),
    };
  }, [sessionId, cards, agentUiComponent]);
}
