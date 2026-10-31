import { cardsHaveExtraction } from "./rfpFlow";

export async function fetchRfpCards(sessionId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/rfp/${sessionId}/cards/`, { credentials: "include" });
  if (!res.ok) return {};
  const data = await res.json();
  return (data.cards as Record<string, unknown>) || {};
}

/** Poll until cards exist or attempts exhausted (debate may finish after HTTP create). */
export async function waitForRfpCards(
  sessionId: string,
  opts?: { attempts?: number; delayMs?: number },
): Promise<Record<string, unknown>> {
  const attempts = opts?.attempts ?? 8;
  const delayMs = opts?.delayMs ?? 400;
  for (let i = 0; i < attempts; i += 1) {
    const cards = await fetchRfpCards(sessionId);
    if (cardsHaveExtraction(cards)) return cards;
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return fetchRfpCards(sessionId);
}
