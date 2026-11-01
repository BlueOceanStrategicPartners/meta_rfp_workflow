import { cardsHaveExtraction } from "./rfpFlow";
import { apiFetch } from "./apiClient";

export type CreateRfpSessionResult =
  | {
      ok: true;
      id: string;
      voiceIntro: string;
      cards: Record<string, unknown>;
    }
  | { ok: false; message: string };

export async function createRfpSession(
  sourceText: string,
  runDebate: boolean,
): Promise<CreateRfpSessionResult> {
  let res: Response;
  try {
    res = await apiFetch("/api/rfp/", {
      method: "POST",
      body: JSON.stringify({
        source_document_text: sourceText.slice(0, 5000) || "Corporate RFP",
        run_debate: runDebate,
      }),
    });
  } catch {
    return {
      ok: false,
      message:
        "Cannot reach the API. Start the backend with scripts/dev-backend.ps1 (http://127.0.0.1:8000).",
    };
  }

  if (!res.ok) {
    let message = `RFP session failed (HTTP ${res.status}).`;
    if (res.status === 502 || res.status === 503 || res.status === 504) {
      message =
        "Backend unreachable on port 8000. Run scripts/dev-backend.ps1, then refresh this page.";
    } else {
      try {
        const body = (await res.json()) as { detail?: string };
        if (body.detail) message = String(body.detail);
      } catch {
        /* ignore */
      }
    }
    return { ok: false, message };
  }

  const data = await res.json();
  return {
    ok: true,
    id: String(data.id),
    voiceIntro: String(data.voice_intro || ""),
    cards: (data.active_ui_cards_json as Record<string, unknown>) || {},
  };
}

export async function fetchRfpCards(sessionId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/rfp/${sessionId}/cards/`, { credentials: "include" });
  if (!res.ok) return {};
  const data = await res.json();
  return (data.cards as Record<string, unknown>) || {};
}

/** Poll until cards exist or attempts exhausted (debate runs async after HTTP create). */
export async function waitForRfpCards(
  sessionId: string,
  opts?: { attempts?: number; delayMs?: number },
): Promise<Record<string, unknown>> {
  const attempts = opts?.attempts ?? 40;
  const delayMs = opts?.delayMs ?? 750;
  for (let i = 0; i < attempts; i += 1) {
    const cards = await fetchRfpCards(sessionId);
    if (cardsHaveExtraction(cards)) return cards;
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return fetchRfpCards(sessionId);
}
