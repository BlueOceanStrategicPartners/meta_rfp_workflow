import { parseUiComponent, type AgentUiComponent } from "./agentUiComponents";

export type { AgentUiComponent };

export type VoiceChatStreamHandlers = {
  onStatus?: (text: string) => void;
  onToken?: (text: string) => void;
  onDone?: (reply: string, uiComponent?: AgentUiComponent | null) => void;
  onError?: (message: string) => void;
};

export type VoiceChatTurnResult = {
  reply: string;
  uiComponent: AgentUiComponent | null;
};

/** POST + SSE progressive assistant reply (status → tokens → done). Falls back to JSON chat if stream unavailable. */
export async function streamAssistantReply(
  message: string,
  rfpId: string | null,
  handlers: VoiceChatStreamHandlers,
  signal?: AbortSignal,
): Promise<VoiceChatTurnResult> {
  try {
    const res = await fetch("/api/negotiation/voice-chat/stream/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      credentials: "include",
      signal,
      body: JSON.stringify({ message, rfp_id: rfpId }),
    });

    if (!res.ok || !res.body) {
      return fetchBlockingAssistantReply(message, rfpId, handlers, signal);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let reply = "";
    let uiComponent: AgentUiComponent | null = null;

    const dispatch = (block: string) => {
      const lines = block.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) return;
      try {
        const payload = JSON.parse(data) as Record<string, unknown>;
        if (event === "status" && typeof payload.text === "string") {
          handlers.onStatus?.(payload.text);
        } else if (event === "token" && typeof payload.text === "string") {
          handlers.onToken?.(payload.text);
        } else if (event === "done" && typeof payload.reply === "string") {
          reply = payload.reply;
          uiComponent = parseUiComponent(payload.ui_component);
          handlers.onDone?.(reply, uiComponent);
        } else if (event === "error" && typeof payload.message === "string") {
          handlers.onError?.(payload.message);
        }
      } catch {
        /* ignore malformed chunk */
      }
    };

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let splitAt = buffer.indexOf("\n\n");
      while (splitAt >= 0) {
        dispatch(buffer.slice(0, splitAt));
        buffer = buffer.slice(splitAt + 2);
        splitAt = buffer.indexOf("\n\n");
      }
    }

    if (buffer.trim()) dispatch(buffer.trim());

    if (reply) return { reply, uiComponent };
    return fetchBlockingAssistantReply(message, rfpId, handlers, signal);
  } catch {
    return fetchBlockingAssistantReply(message, rfpId, handlers, signal);
  }
}

async function fetchBlockingAssistantReply(
  message: string,
  rfpId: string | null,
  handlers: VoiceChatStreamHandlers,
  signal?: AbortSignal,
): Promise<VoiceChatTurnResult> {
  handlers.onStatus?.("Connecting to the assistant…");
  try {
    const res = await fetch("/api/negotiation/voice-chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      signal,
      body: JSON.stringify({ message, rfp_id: rfpId }),
    });
    if (!res.ok) {
      let detail = "";
      try {
        const body = (await res.json()) as { detail?: string; message?: string };
        detail = String(body.detail || body.message || "").trim();
      } catch {
        /* ignore */
      }
      const fallback = detail
        ? detail
        : `I'm having trouble reaching the assistant (HTTP ${res.status}). Check that the backend is running on port 8000.`;
      handlers.onError?.(fallback);
      return { reply: fallback, uiComponent: null };
    }
    const data = (await res.json()) as { reply?: string; ui_component?: unknown };
    const reply = String(data.reply || "I'm here to help with your RFP.");
    const uiComponent = parseUiComponent(data.ui_component);
    handlers.onDone?.(reply, uiComponent);
    return { reply, uiComponent };
  } catch {
    const fallback = "I'm having trouble reaching the assistant. Please try again in a moment.";
    handlers.onError?.(fallback);
    return { reply: fallback, uiComponent: null };
  }
}
