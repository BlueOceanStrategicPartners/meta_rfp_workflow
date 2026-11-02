import type { MutableRefObject } from "react";
import { flushSync } from "react-dom";
import type { AgentPreviewSnapshot, AgentToolStep, AgentWorkPlanStep } from "./designerChatStream";
import { normalizeAgentWorkPlanSteps } from "./designerChatStream";
import type { DesignerLiveProgress } from "./designerApi";
import { isPlanningOnlyTodos } from "./designerAgentTodos";
import { normalizeDesignerProgressLabel } from "./designerUserLabels";

export type LiveProgressApplyRefs = {
  agentTodosRef: MutableRefObject<AgentWorkPlanStep[]>;
  agentToolStepsRef: MutableRefObject<AgentToolStep[]>;
};

export type LiveProgressApplyHandlers = LiveProgressApplyRefs & {
  setAgentWorkPlan: (steps: AgentWorkPlanStep[]) => void;
  setAgentTodos: (todos: AgentWorkPlanStep[]) => void;
  setAgentToolSteps: (steps: AgentToolStep[]) => void;
  applyPreview?: (snap: AgentPreviewSnapshot) => void;
};

/** Apply poll/resume snapshot to agent progress UI (SSE fallback). Returns true if a run is active. */
export function applyDesignerLiveProgressSnapshot(
  snap: DesignerLiveProgress,
  handlers: LiveProgressApplyHandlers,
): boolean {
  if (!snap.active) return false;

  flushSync(() => {
    if (snap.work_plan?.length) {
      handlers.setAgentWorkPlan(normalizeAgentWorkPlanSteps(snap.work_plan));
      if (isPlanningOnlyTodos(handlers.agentTodosRef.current)) {
        handlers.agentTodosRef.current = [];
        handlers.setAgentTodos([]);
      }
    }
    if (snap.agent_todos?.length) {
      const normalized = normalizeAgentWorkPlanSteps(snap.agent_todos);
      if (normalized.length > 0 && !isPlanningOnlyTodos(normalized)) {
        handlers.agentTodosRef.current = normalized;
        handlers.setAgentTodos(normalized);
      }
    }
    if (snap.tool_steps?.length) {
      const mapped: AgentToolStep[] = snap.tool_steps.map((t) => ({
        tool: String(t.tool ?? ""),
        label: normalizeDesignerProgressLabel(String(t.label ?? "")),
        ok: Boolean(t.ok),
        phase: t.phase === "repair" ? "repair" : "edit",
      }));
      const next = mapped.slice(-24);
      handlers.agentToolStepsRef.current = next;
      handlers.setAgentToolSteps(next);
    }
    if (handlers.applyPreview && (snap.preview?.html_markup || snap.preview?.css_stylesheet)) {
      handlers.applyPreview({
        html_markup: String(snap.preview?.html_markup ?? ""),
        css_stylesheet: String(snap.preview?.css_stylesheet ?? ""),
        js_script: String(snap.preview?.js_script ?? ""),
      });
    }
  });

  return true;
}
