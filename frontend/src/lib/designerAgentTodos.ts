import type { AgentWorkPlanStep } from "./designerChatStream";

/** Shown immediately on send until SSE `todo` events arrive. */
export const PLANNING_WAIT_TODOS: AgentWorkPlanStep[] = [
  {
    id: "planning",
    label: "Creating your to-do list from this request…",
    status: "active",
  },
];

export function isPlanningOnlyTodos(todos: AgentWorkPlanStep[]): boolean {
  return todos.length === 1 && todos[0]?.id === "planning";
}

export function isExecutionTodoList(todos: AgentWorkPlanStep[]): boolean {
  return todos.some((t) => t.id.startsWith("exec_") || t.id === "finalize");
}

/** True when the todo list should show an in-progress spinner (not a completed checklist). */
export function todosIndicateActiveRun(todos: AgentWorkPlanStep[]): boolean {
  if (todos.length === 0 || isPlanningOnlyTodos(todos)) return true;
  return todos.some((t) => t.status === "active" || t.status === "pending");
}

export function todosAllComplete(todos: AgentWorkPlanStep[]): boolean {
  return (
    todos.length > 0 &&
    !isPlanningOnlyTodos(todos) &&
    todos.every((t) => t.status === "done" || t.status === "skipped")
  );
}

/** Drop completed execution todos so the progress card does not hang after a successful turn. */
export function collapseCompletedExecutionTodos(todos: AgentWorkPlanStep[]): AgentWorkPlanStep[] {
  if (!todosAllComplete(todos)) return todos;
  return [];
}
