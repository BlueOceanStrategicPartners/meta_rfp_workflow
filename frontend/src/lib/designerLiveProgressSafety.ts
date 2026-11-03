import type { DesignerLiveProgress } from "./designerApi";

const MAX_RESUME_AGE_MS = 120_000;

/** True when the server snapshot carries real in-flight work (not a stale active flag). */
export function liveProgressSnapshotHasWork(snap: DesignerLiveProgress): boolean {
  if (!snap.active) return false;
  const todos = snap.agent_todos?.length ?? 0;
  const plan = snap.work_plan?.length ?? 0;
  const tools = snap.tool_steps?.length ?? 0;
  const preview = Boolean(
    (snap.preview?.html_markup || "").trim() || (snap.preview?.css_stylesheet || "").trim(),
  );
  return todos > 0 || plan > 0 || tools > 0 || preview;
}

/** Whether a reload should resume the busy spinner (never on empty ghost active). */
export function shouldResumeBusyFromLiveProgress(snap: DesignerLiveProgress): boolean {
  if (!liveProgressSnapshotHasWork(snap)) return false;
  const updated = snap.updated_at;
  if (typeof updated !== "number" || !Number.isFinite(updated)) return false;
  const ageMs = Date.now() - updated * 1000;
  return ageMs >= 0 && ageMs <= MAX_RESUME_AGE_MS;
}
