import type { AgentWorkPlanStep } from "./designerChatStream";
import { isPlanningOnlyTodos, todosIndicateActiveRun } from "./designerAgentTodos";

export type AgentPartialProgress = {
  completed: Array<{ id: string; label: string; ok: boolean }>;
  remaining: string[];
} | null;

export type AgentProgressUiInput = {
  busy: boolean;
  agentTodos: AgentWorkPlanStep[];
  agentPartialProgress: AgentPartialProgress;
};

export type AgentProgressUi = {
  /** Progress card visible (spinner, todos, or partial-completion panel). */
  showProgressCard: boolean;
  /** Second preview iframe — only during an in-flight chat stream. */
  showProgressIframe: boolean;
  /** Card shows active/spinner state (not only continuation panel). */
  progressActive: boolean;
};

/**
 * Single source of truth for agent progress UI (Checkmate terminal states).
 * Invariants:
 * - Empty todos never imply an active run.
 * - WIP iframe only while `busy` (user sent a message this session).
 * - Partial-completion panel never mounts the WIP iframe.
 */
export function resolveAgentProgressUi(input: AgentProgressUiInput): AgentProgressUi {
  const hasPartial = Boolean(input.agentPartialProgress);
  const todosActive =
    input.agentTodos.length > 0 && todosIndicateActiveRun(input.agentTodos);

  const progressActive = input.busy || hasPartial || todosActive;
  const showProgressCard = progressActive;
  const showProgressIframe = input.busy && !hasPartial;

  if (import.meta.env.DEV) {
    if (input.agentTodos.length === 0 && todosActive) {
      console.error("[designer] invariant violated: empty todos marked active");
    }
    if (showProgressIframe && !input.busy) {
      console.error("[designer] invariant violated: progress iframe without busy");
    }
  }

  return { showProgressCard, showProgressIframe, progressActive };
}

/** Sanitize todos restored from chat history / poll — drop stuck finalize-only lists. */
export function sanitizeRestoredAgentTodos(todos: AgentWorkPlanStep[]): AgentWorkPlanStep[] {
  if (todos.length === 0 || isPlanningOnlyTodos(todos)) return [];
  const activeOrPending = todos.filter((t) => t.status === "active" || t.status === "pending");
  if (activeOrPending.length === 0) return [];
  return activeOrPending;
}
