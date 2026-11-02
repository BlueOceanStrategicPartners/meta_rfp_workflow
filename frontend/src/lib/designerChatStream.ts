import { getDesignerStreamPostHeaders, resolveDevStreamUrl } from "./apiClient";
import { designerChat, type ChatMessage, type DesignerChatResponse, type PreviewAutomationReport } from "./designerApi";
import { normalizeDesignerProgressLabel } from "./designerUserLabels";

export type AgentToolStep = {
  tool: string;
  label: string;
  ok: boolean;
  phase?: "edit" | "repair";
};

export type AgentProgressItem = {
  id: string;
  label: string;
  ok: boolean;
};

export type AgentWorkPlanStep = {
  id: string;
  label: string;
  status: "pending" | "active" | "done" | "skipped";
};

export type AgentPreviewSnapshot = {
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
};

export type DesignerChatStreamHandlers = {
  onPlan?: (steps: AgentWorkPlanStep[]) => void;
  onStep?: (steps: AgentWorkPlanStep[]) => void;
  onTodo?: (todos: AgentWorkPlanStep[]) => void;
  onPreview?: (snapshot: AgentPreviewSnapshot) => void;
  onTool?: (step: AgentToolStep) => void;
  onDone?: (response: DesignerChatResponse) => void;
  onError?: (message: string) => void;
  onStatus?: (payload: { kind: string; message?: string; partial?: boolean }) => void;
};

export type DesignerChatRequestBody = {
  message: string;
  history: ChatMessage[];
  html_markup: string;
  css_stylesheet: string;
  js_script: string;
  attachment_ids?: string[];
  template_id?: string;
  include_preview_audit?: boolean;
  preview_automation_report?: PreviewAutomationReport | null;
  preview_automation_depth?: number;
};

function normalizeSseText(text: string): string {
  return text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

const TODO_STATUSES = new Set<AgentWorkPlanStep["status"]>(["pending", "active", "done", "skipped"]);

/** Coerce backend todo snapshots into stable React state (always new array). */
export function normalizeAgentWorkPlanSteps(raw: unknown): AgentWorkPlanStep[] {
  if (!Array.isArray(raw)) return [];
  const out: AgentWorkPlanStep[] = [];
  for (let idx = 0; idx < raw.length; idx += 1) {
    const item = raw[idx];
    if (!item || typeof item !== "object") continue;
    const rec = item as Record<string, unknown>;
    const label = String(rec.label ?? "").trim();
    if (!label) continue;
    const id = String(rec.id ?? `step-${idx}`);
    let status = String(rec.status ?? "pending") as AgentWorkPlanStep["status"];
    if (!TODO_STATUSES.has(status)) status = "pending";
    out.push({ id, label: normalizeDesignerProgressLabel(label), status });
  }
  return out;
}

function parseSseBlock(block: string): { event: string; data: string } {
  const lines = normalizeSseText(block).split("\n");
  let event = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) {
      const chunk = line.slice(5).trimStart();
      data = data ? `${data}\n${chunk}` : chunk;
    }
  }
  return { event, data };
}

function drainSseBuffer(buffer: string, dispatch: (block: string) => void): string {
  let rest = normalizeSseText(buffer);
  let splitAt = rest.indexOf("\n\n");
  while (splitAt >= 0) {
    dispatch(rest.slice(0, splitAt));
    rest = rest.slice(splitAt + 2);
    splitAt = rest.indexOf("\n\n");
  }
  return rest;
}

function createSseDispatcher(handlers: DesignerChatStreamHandlers) {
  let finalResponse: DesignerChatResponse | null = null;

  const dispatch = (block: string) => {
    const { event, data } = parseSseBlock(block);
    if (!data) return;
    try {
      const payload = JSON.parse(data) as Record<string, unknown>;
      const eventName = event.trim().toLowerCase();
      if (eventName === "plan" && Array.isArray(payload.steps)) {
        handlers.onPlan?.(normalizeAgentWorkPlanSteps(payload.steps));
      } else if (eventName === "todo" && Array.isArray(payload.todos)) {
        const todos = normalizeAgentWorkPlanSteps(payload.todos);
        if (import.meta.env.DEV) {
          const w = window as Window & { __designerSseTodo?: { n: number; at: number; ids: string[] } };
          w.__designerSseTodo = {
            n: (w.__designerSseTodo?.n ?? 0) + 1,
            at: Date.now(),
            ids: todos.map((t) => `${t.id}:${t.status}`),
          };
        }
        handlers.onTodo?.(todos);
      } else if (eventName === "step" && Array.isArray(payload.steps)) {
        handlers.onStep?.(normalizeAgentWorkPlanSteps(payload.steps));
      } else if (eventName === "tool" && typeof payload.label === "string") {
        handlers.onTool?.({
          tool: String(payload.tool ?? ""),
          label: normalizeDesignerProgressLabel(String(payload.label)),
          ok: Boolean(payload.ok),
          phase: payload.phase === "repair" ? "repair" : "edit",
        });
      } else if (eventName === "preview") {
        handlers.onPreview?.({
          html_markup: String(payload.html_markup ?? ""),
          css_stylesheet: String(payload.css_stylesheet ?? ""),
          js_script: String(payload.js_script ?? ""),
        });
      } else if (eventName === "done") {
        finalResponse = payload as DesignerChatResponse;
        const doneTodos = normalizeAgentWorkPlanSteps(finalResponse.agent_todos);
        if (doneTodos.length > 0) {
          handlers.onTodo?.(doneTodos);
        }
        handlers.onDone?.(finalResponse);
      } else if (eventName === "status" && typeof payload.kind === "string") {
        handlers.onStatus?.({
          kind: String(payload.kind),
          message: typeof payload.message === "string" ? payload.message : undefined,
          partial: Boolean(payload.partial),
        });
      } else if (eventName === "error" && typeof payload.message === "string") {
        handlers.onError?.(payload.message);
      } else if (eventName === "cancelled") {
        throw new DOMException("Design agent stopped", "AbortError");
      }
    } catch (err) {
      if (import.meta.env.DEV) {
        console.warn("[designer SSE] dropped block", event, err);
      }
    }
  };

  return {
    dispatch,
    getFinal: () => finalResponse,
    flushTail: (tail: string) => {
      const trimmed = tail.trim();
      if (trimmed) dispatch(trimmed);
    },
  };
}

/** Fetch ReadableStream fallback when XHR streaming is unavailable. */
async function streamDesignerChatViaFetch(
  url: string,
  bodyJson: string,
  headers: Record<string, string>,
  handlers: DesignerChatStreamHandlers,
  signal?: AbortSignal,
): Promise<DesignerChatResponse | null> {
  const { dispatch, getFinal, flushTail } = createSseDispatcher(handlers);

  const res = await fetch(url, {
    method: "POST",
    headers: { ...headers },
    body: bodyJson,
    credentials: "include",
    signal,
    cache: "no-store",
  });

  if (res.status === 406) {
    throw new Error("SSE_NOT_ACCEPTED");
  }
  if (!res.ok) {
    throw new Error(`Design agent stream failed (HTTP ${res.status})`);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("Design agent stream has no response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = drainSseBuffer(buffer, dispatch);
  }
  buffer += decoder.decode();
  buffer = drainSseBuffer(buffer, dispatch);
  flushTail(buffer);
  return getFinal();
}

/** XHR onprogress delivers SSE incrementally (fetch body stream often batches on POST). */
function streamDesignerChatViaXhr(
  url: string,
  bodyJson: string,
  headers: Record<string, string>,
  handlers: DesignerChatStreamHandlers,
  signal?: AbortSignal,
): Promise<DesignerChatResponse | null> {
  const { dispatch, getFinal, flushTail } = createSseDispatcher(handlers);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.responseType = "text";
    for (const [key, value] of Object.entries(headers)) {
      xhr.setRequestHeader(key, value);
    }
    let buffer = "";
    let lastLen = 0;

    const drainIncremental = () => {
      const text = xhr.responseText;
      if (text.length <= lastLen) return;
      buffer += text.slice(lastLen);
      lastLen = text.length;
      buffer = drainSseBuffer(buffer, dispatch);
    };

    xhr.onreadystatechange = () => {
      if (xhr.readyState >= 3) drainIncremental();
    };
    xhr.onprogress = drainIncremental;

    const onAbort = () => {
      xhr.abort();
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });

    xhr.onload = () => {
      signal?.removeEventListener("abort", onAbort);
      const text = xhr.responseText;
      if (text.length > lastLen) {
        buffer += text.slice(lastLen);
      }
      buffer = drainSseBuffer(buffer, dispatch);
      flushTail(buffer);

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(getFinal());
        return;
      }
      if (xhr.status === 406) {
        reject(new Error("SSE_NOT_ACCEPTED"));
        return;
      }
      reject(new Error(`Design agent stream failed (HTTP ${xhr.status})`));
    };

    xhr.onerror = () => {
      signal?.removeEventListener("abort", onAbort);
      reject(new Error("Design agent stream network error"));
    };

    xhr.send(bodyJson);
  });
}

/** SSE work-plan progress during design agent turns; falls back to blocking chat. */
export async function streamDesignerChat(
  body: DesignerChatRequestBody,
  handlers: DesignerChatStreamHandlers,
  signal?: AbortSignal,
): Promise<DesignerChatResponse> {
  try {
    const streamUrl = resolveDevStreamUrl("/api/designer/chat/stream/");
    const bodyJson = JSON.stringify(body);
    const headers = await getDesignerStreamPostHeaders();

    let finalResponse: DesignerChatResponse | null = null;
    try {
      // Prefer fetch ReadableStream (works in some embedded webviews); XHR fallback.
      finalResponse = await streamDesignerChatViaFetch(streamUrl, bodyJson, headers, handlers, signal);
    } catch (fetchErr) {
      if (signal?.aborted || (fetchErr instanceof DOMException && fetchErr.name === "AbortError")) {
        throw fetchErr;
      }
      const fetchMsg = fetchErr instanceof Error ? fetchErr.message : "";
      if (fetchMsg === "SSE_NOT_ACCEPTED") {
        handlers.onError?.(
          "Live progress unavailable (stream not accepted). Retrying with standard chat — to-dos may update only at the end.",
        );
        const fallback = await designerChat(body);
        if (signal?.aborted) {
          throw new DOMException("Aborted", "AbortError");
        }
        handlers.onPlan?.(fallback.work_plan ?? []);
        if (fallback.agent_todos?.length) {
          handlers.onTodo?.(fallback.agent_todos);
        }
        handlers.onDone?.(fallback);
        return fallback;
      }
      try {
        finalResponse = await streamDesignerChatViaXhr(streamUrl, bodyJson, headers, handlers, signal);
      } catch (xhrErr) {
        if (signal?.aborted || (xhrErr instanceof DOMException && xhrErr.name === "AbortError")) {
          throw xhrErr;
        }
        console.warn("Design agent fetch stream failed, XHR retry failed:", fetchErr, xhrErr);
        throw fetchErr;
      }
    }

    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    if (finalResponse) return finalResponse;

    const fallback = await designerChat(body);
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    handlers.onPlan?.(fallback.work_plan ?? []);
    if (fallback.agent_todos?.length) {
      handlers.onTodo?.(fallback.agent_todos);
    }
    handlers.onDone?.(fallback);
    return fallback;
  } catch (err) {
    if (signal?.aborted || (err instanceof DOMException && err.name === "AbortError")) {
      throw err;
    }
    const msg = err instanceof Error ? err.message : "Design agent request failed.";
    handlers.onError?.(msg);
    throw err;
  }
}
