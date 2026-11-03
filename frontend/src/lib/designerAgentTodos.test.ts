import { describe, expect, it } from "vitest";
import {
  PLANNING_WAIT_TODOS,
  collapseCompletedExecutionTodos,
  todosIndicateActiveRun,
} from "./designerAgentTodos";
import { resolveAgentProgressUi, sanitizeRestoredAgentTodos } from "./designerProgressState";
import {
  liveProgressSnapshotHasWork,
  shouldResumeBusyFromLiveProgress,
} from "./designerLiveProgressSafety";

describe("todosIndicateActiveRun", () => {
  it("returns false for empty todos (idle Designer load)", () => {
    expect(todosIndicateActiveRun([])).toBe(false);
  });

  it("returns true for planning placeholder during send", () => {
    expect(todosIndicateActiveRun(PLANNING_WAIT_TODOS)).toBe(true);
  });

  it("returns true when execution todo is pending", () => {
    expect(
      todosIndicateActiveRun([{ id: "exec_1", label: "Edit", status: "pending" }]),
    ).toBe(true);
  });
});

describe("resolveAgentProgressUi", () => {
  it("idle: no card, no iframe", () => {
    const ui = resolveAgentProgressUi({
      busy: false,
      agentTodos: [],
      agentPartialProgress: null,
    });
    expect(ui.showProgressCard).toBe(false);
    expect(ui.showProgressIframe).toBe(false);
    expect(ui.progressActive).toBe(false);
  });

  it("busy run: card + iframe, not when only partial completion", () => {
    const run = resolveAgentProgressUi({
      busy: true,
      agentTodos: [{ id: "exec_1", label: "x", status: "active" }],
      agentPartialProgress: null,
    });
    expect(run.showProgressIframe).toBe(true);

    const partial = resolveAgentProgressUi({
      busy: false,
      agentTodos: [],
      agentPartialProgress: { completed: [], remaining: ["Fix nav"] },
    });
    expect(partial.showProgressCard).toBe(true);
    expect(partial.showProgressIframe).toBe(false);
  });

  it("never iframe when busy false even if todos were wrongly active", () => {
    const ui = resolveAgentProgressUi({
      busy: false,
      agentTodos: [{ id: "exec_1", label: "x", status: "active" }],
      agentPartialProgress: null,
    });
    expect(ui.showProgressIframe).toBe(false);
  });
});

describe("liveProgressSnapshotHasWork", () => {
  it("rejects active flag with empty payload", () => {
    expect(liveProgressSnapshotHasWork({ active: true })).toBe(false);
  });

  it("accepts active with todos", () => {
    expect(
      liveProgressSnapshotHasWork({
        active: true,
        agent_todos: [{ id: "a", label: "b", status: "active" }],
      }),
    ).toBe(true);
  });
});

describe("shouldResumeBusyFromLiveProgress", () => {
  it("rejects stale timestamps", () => {
    const old = Date.now() / 1000 - 600;
    expect(
      shouldResumeBusyFromLiveProgress({
        active: true,
        updated_at: old,
        agent_todos: [{ id: "a", label: "b", status: "active" }],
      }),
    ).toBe(false);
  });
});

describe("sanitizeRestoredAgentTodos", () => {
  it("drops planning-only and all-done lists", () => {
    expect(sanitizeRestoredAgentTodos(PLANNING_WAIT_TODOS)).toEqual([]);
    expect(
      sanitizeRestoredAgentTodos([
        { id: "exec_1", label: "x", status: "done" },
        { id: "finalize", label: "y", status: "done" },
      ]),
    ).toEqual([]);
  });
});

describe("collapseCompletedExecutionTodos", () => {
  it("clears completed execution list", () => {
    expect(
      collapseCompletedExecutionTodos([
        { id: "exec_1", label: "x", status: "done" },
        { id: "finalize", label: "y", status: "done" },
      ]),
    ).toEqual([]);
  });
});
