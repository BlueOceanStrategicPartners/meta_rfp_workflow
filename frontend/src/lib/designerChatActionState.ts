import type { AgentProgressItem, AgentWorkPlanStep } from "./designerChatStream";
import type { ChatMessage, DesignerChatActionState } from "./designerApi";
import { collapseCompletedExecutionTodos } from "./designerAgentTodos";

export type RestoredDesignerActionUi = {
  partialProgress: {
    completed: AgentProgressItem[];
    remaining: string[];
  } | null;
  clarifications: string[];
  agentTodos: AgentWorkPlanStep[];
};

const DEFAULT_CONTINUE_OPTIONS = [
  "Continue — finish the remaining edits",
  "Continue — focus on validation issues only",
  "Stop here — I'll adjust manually",
];

function legacyActionStateFromAgentFailure(content: string): DesignerChatActionState | null {
  const text = content || "";
  if (
    !/executor agent failed|unexpected error while working|design assistant hit|user_model_turn_label/i.test(
      text,
    )
  ) {
    return null;
  }
  return {
    partial_completion: true,
    continuation_recommended: true,
    remaining_items: ["Retry or continue your last design request"],
    progress_completed: [],
    clarification_options: ["Retry the request", "Continue — finish the remaining edits"],
  };
}

function legacyActionStateFromAssistantContent(content: string): DesignerChatActionState | null {
  const failure = legacyActionStateFromAgentFailure(content);
  if (failure) return failure;
  const text = content || "";
  if (!/step limit|progress card below|partial completion/i.test(text)) {
    return null;
  }
  if (/tap Continue to resume/i.test(text) && !/\*\*Still open:\*\*/i.test(text)) {
    // New short message format without embedded lists — still actionable
    return {
      partial_completion: true,
      continuation_recommended: true,
      remaining_items: ["Remaining edits from your last request"],
      progress_completed: [],
      clarification_options: DEFAULT_CONTINUE_OPTIONS,
    };
  }

  let progress_completed: AgentProgressItem[] = [];
  const completedMatch = text.match(/\*\*Completed so far:\*\*\s*([\s\S]*?)(?:\n\n\*\*Still open:\*\*|\n\nChoose|\z)/i);
  if (completedMatch) {
    const lines = completedMatch[1]
      .split("\n")
      .map((l) => l.replace(/^[-*]\s*/, "").trim())
      .filter(Boolean);
    const seen = new Set<string>();
    for (const line of lines) {
      if (seen.has(line)) continue;
      seen.add(line);
      progress_completed.push({ id: `legacy-${progress_completed.length}`, label: line, ok: true });
    }
  }

  let remaining_items: string[] = [];
  const openMatch = text.match(/\*\*Still open:\*\*\s*([\s\S]*?)(?:\n\nChoose|\z)/i);
  if (openMatch) {
    remaining_items = openMatch[1]
      .split("\n")
      .map((l) => l.replace(/^[-*]\s*/, "").trim())
      .filter(Boolean);
  }

  if (!remaining_items.length && !progress_completed.length) {
    return null;
  }

  return {
    partial_completion: true,
    continuation_recommended: true,
    remaining_items,
    progress_completed,
    clarification_options: DEFAULT_CONTINUE_OPTIONS,
  };
}

export function findLatestAssistantActionState(
  history: ChatMessage[],
): DesignerChatActionState | null {
  for (let i = history.length - 1; i >= 0; i--) {
    const msg = history[i];
    if (msg.role !== "assistant") continue;
    if (msg.action_state && !msg.action_state.dismissed) {
      return msg.action_state;
    }
    const legacy = legacyActionStateFromAssistantContent(msg.content);
    if (legacy) return legacy;
    // Newest assistant has no Continue/Retry card — ignore older turns.
    return null;
  }
  return null;
}

export function restoreDesignerActionUi(history: ChatMessage[]): RestoredDesignerActionUi {
  const state = findLatestAssistantActionState(history);
  if (!state) {
    return { partialProgress: null, clarifications: [], agentTodos: [] };
  }

  const clarifications = state.clarification_options ?? [];
  let agentTodos = state.agent_todos ?? [];
  if (!state.partial_completion) {
    agentTodos = collapseCompletedExecutionTodos(agentTodos);
    const execDone =
      agentTodos.filter((t) => t.id.startsWith("exec_")).length === 0 ||
      agentTodos
        .filter((t) => t.id.startsWith("exec_"))
        .every((t) => t.status === "done" || t.status === "skipped");
    const finalizeStuck =
      agentTodos.some((t) => t.id === "finalize" && t.status === "active") && execDone;
    if (finalizeStuck) {
      agentTodos = [];
    } else {
      agentTodos = agentTodos.filter((t) => t.status === "active" || t.status === "pending");
    }
  }

  if (state.partial_completion && state.continuation_recommended) {
    return {
      partialProgress: {
        completed: state.progress_completed ?? [],
        remaining: state.remaining_items ?? [],
      },
      clarifications,
      agentTodos,
    };
  }

  if (clarifications.length > 0) {
    return { partialProgress: null, clarifications, agentTodos };
  }

  return { partialProgress: null, clarifications: [], agentTodos };
}

/** Mark the latest actionable assistant turn as dismissed (Continue card closed). */
export function dismissLatestAssistantActionState(history: ChatMessage[]): ChatMessage[] {
  const next = history.map((m) => ({ ...m }));
  for (let i = next.length - 1; i >= 0; i--) {
    const msg = next[i];
    if (msg.role === "assistant" && msg.action_state && !msg.action_state.dismissed) {
      next[i] = {
        ...msg,
        action_state: { ...msg.action_state, dismissed: true },
      };
      break;
    }
  }
  return next;
}
