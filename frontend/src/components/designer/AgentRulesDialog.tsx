import { useCallback, useEffect, useState } from "react";
import {
  createDesignerAgentRule,
  deleteDesignerAgentRule,
  listDesignerAgentRules,
  updateDesignerAgentRule,
  validateDesignerAgentRule,
  type DesignerAgentRule,
} from "../../lib/designerAgentRulesApi";
import { IconAgentRules } from "./TemplateIconButton";

function AgentRulesEmptyState() {
  return (
    <div
      className="rounded-2xl border border-dashed border-violet-400/25 bg-gradient-to-b from-violet-500/[0.08] via-transparent to-transparent px-4 py-6 text-center sm:px-5"
      role="status"
    >
      <div
        className="mx-auto mb-4 flex h-[3.25rem] w-[3.25rem] items-center justify-center rounded-2xl border border-violet-400/30 bg-violet-500/15 text-violet-200 shadow-[0_0_24px_-8px_rgba(139,92,246,0.55)]"
        aria-hidden
      >
        <IconAgentRules size={28} />
      </div>
      <p className="text-sm font-semibold text-white/92">No agent rules yet</p>
      <p className="mx-auto mt-2 max-w-[19rem] text-pretty text-xs leading-relaxed text-white/55">
        Add plain-language instructions for layout, tone, dates, CTAs, and brand guardrails. The design agent pulls the
        most relevant rules on every turn.
      </p>
      <ul className="mx-auto mt-4 max-w-[17rem] space-y-1.5 text-left text-[11px] text-white/45">
        <li className="flex gap-2">
          <span className="mt-0.5 text-violet-400/90" aria-hidden>
            •
          </span>
          <span>Conflicts are checked before a rule is saved.</span>
        </li>
        <li className="flex gap-2">
          <span className="mt-0.5 text-violet-400/90" aria-hidden>
            •
          </span>
          <span>Hybrid semantic + keyword match keeps context focused.</span>
        </li>
      </ul>
      <p className="mt-5 text-[10px] font-medium uppercase tracking-wider text-violet-300/75">
        Start with the field below
      </p>
    </div>
  );
}

function AgentRulesLoadingState() {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] px-5 py-10 text-center" role="status" aria-live="polite">
      <div className="mx-auto mb-3 flex h-[3.25rem] w-[3.25rem] animate-pulse items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-white/40">
        <IconAgentRules size={28} />
      </div>
      <p className="text-xs text-white/45">Loading your rules…</p>
    </div>
  );
}

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function AgentRulesDialog({ open, onClose }: Props) {
  const [rules, setRules] = useState<DesignerAgentRule[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [conflict, setConflict] = useState<{
    explanation: string;
    suggested: string;
    ids: string[];
  } | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");

  const refresh = useCallback(async () => {
    setRules(await listDesignerAgentRules());
  }, []);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setConflict(null);
    setDraft("");
    setEditingId(null);
    setLoadState("loading");
    void refresh()
      .then(() => setLoadState("ready"))
      .catch((err: unknown) => {
        setRules([]);
        setLoadState("error");
        setError(err instanceof Error ? err.message : "Could not load rules.");
      });
  }, [open, refresh]);

  const runValidate = async (body: string, excludeRuleId?: string) => {
    const result = await validateDesignerAgentRule(body, excludeRuleId);
    if (result.has_conflict) {
      setConflict({
        explanation: result.explanation,
        suggested: result.suggested_rule,
        ids: result.conflicting_rule_ids,
      });
      return false;
    }
    setConflict(null);
    return true;
  };

  const addRule = async () => {
    const body = draft.trim();
    if (!body) return;
    setBusy(true);
    setError(null);
    try {
      const ok = await runValidate(body);
      if (!ok) return;
      await createDesignerAgentRule(body, rules.length);
      setDraft("");
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not save rule.");
    } finally {
      setBusy(false);
    }
  };

  const saveEdit = async (rule: DesignerAgentRule) => {
    const body = editDraft.trim();
    if (!body) return;
    setBusy(true);
    setError(null);
    try {
      const ok = await runValidate(body, rule.id);
      if (!ok) return;
      await updateDesignerAgentRule(rule.id, { body });
      setEditingId(null);
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not update rule.");
    } finally {
      setBusy(false);
    }
  };

  const applySuggested = async () => {
    if (!conflict?.suggested) return;
    setDraft(conflict.suggested);
    setConflict(null);
  };

  const addSuggestedAsRule = async () => {
    if (!conflict?.suggested) return;
    setBusy(true);
    try {
      await createDesignerAgentRule(conflict.suggested, rules.length);
      setConflict(null);
      setDraft("");
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not add suggested rule.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 px-4 py-[5vh] backdrop-blur-sm sm:px-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-rules-title"
      onClick={onClose}
    >
      <div
        className="flex h-[90dvh] max-h-[90dvh] min-h-0 w-full max-w-[min(100%,36rem)] flex-col rounded-2xl border border-white/10 bg-[#121828] shadow-2xl sm:max-w-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="shrink-0 border-b border-white/10 px-4 py-3 sm:px-5">
          <h3 id="agent-rules-title" className="text-sm font-semibold text-white">
            Agent rules
          </h3>
          <p className="mt-0.5 text-xs text-white/50">
            Plain-language instructions for the design agent. Retrieved by hybrid semantic + keyword match each turn.
          </p>
        </header>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            className={`studio-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 space-y-3 sm:p-4 ${
              loadState === "ready" && rules.length === 0 ? "flex flex-col justify-center" : ""
            }`}
          >
          {error && <p className="rounded-lg bg-red-950/40 px-3 py-2 text-xs text-red-200">{error}</p>}

          {conflict && (
            <div className="rounded-xl border border-amber-400/35 bg-amber-950/25 p-3 text-xs text-amber-100">
              <p className="font-semibold text-amber-200">Rule conflict</p>
              <p className="mt-1 text-white/80">{conflict.explanation}</p>
              {conflict.suggested ? (
                <p className="mt-2 rounded-lg bg-black/25 p-2 text-white/90">{conflict.suggested}</p>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-2">
                {conflict.suggested ? (
                  <>
                    <button
                      type="button"
                      className="rounded-lg bg-violet-600 px-2.5 py-1 text-[11px] font-medium hover:bg-violet-500"
                      onClick={() => void applySuggested()}
                    >
                      Use suggestion in draft
                    </button>
                    <button
                      type="button"
                      className="rounded-lg border border-violet-400/40 px-2.5 py-1 text-[11px] hover:bg-violet-500/10"
                      onClick={() => void addSuggestedAsRule()}
                      disabled={busy}
                    >
                      Add suggestion to rules
                    </button>
                  </>
                ) : null}
                <button
                  type="button"
                  className="rounded-lg border border-white/15 px-2.5 py-1 text-[11px] text-white/70"
                  onClick={() => setConflict(null)}
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          <ul className="space-y-2">
            {rules.map((rule, idx) => (
              <li
                key={rule.id}
                className="rounded-xl border border-white/10 bg-white/[0.03] p-2.5"
              >
                {editingId === rule.id ? (
                  <>
                    <textarea
                      className="studio-field min-h-[4rem] w-full text-xs"
                      value={editDraft}
                      onChange={(e) => setEditDraft(e.target.value)}
                    />
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        className="rounded-lg bg-violet-600 px-2.5 py-1 text-[11px] font-medium"
                        onClick={() => void saveEdit(rule)}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="rounded-lg border border-white/15 px-2.5 py-1 text-[11px]"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-[11px] leading-snug text-white/85 whitespace-pre-wrap">{rule.body}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
                      <button
                        type="button"
                        className="text-violet-300 hover:underline"
                        onClick={() => {
                          setEditingId(rule.id);
                          setEditDraft(rule.body);
                          setConflict(null);
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="text-red-300 hover:underline"
                        disabled={busy}
                        onClick={() =>
                          void (async () => {
                            setBusy(true);
                            try {
                              await deleteDesignerAgentRule(rule.id);
                              await refresh();
                            } finally {
                              setBusy(false);
                            }
                          })()
                        }
                      >
                        Remove
                      </button>
                      <span className="text-white/30">#{idx + 1}</span>
                    </div>
                  </>
                )}
              </li>
            ))}
            {loadState === "loading" && (
              <li className="list-none">
                <AgentRulesLoadingState />
              </li>
            )}
            {loadState === "ready" && rules.length === 0 && (
              <li className="list-none">
                <AgentRulesEmptyState />
              </li>
            )}
          </ul>
          </div>

          <div className="shrink-0 border-t border-white/10 bg-[#121828] p-3 sm:p-4">
            <label className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-white/40">
              New rule
            </label>
            <textarea
              className="studio-field min-h-[4.5rem] w-full text-xs sm:min-h-[5rem]"
              placeholder="e.g. Always keep the accept CTA visible on desktop and use MM/DD/YYYY for dates."
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <button
              type="button"
              disabled={busy || !draft.trim()}
              className="mt-2 w-full rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 py-2 text-xs font-semibold disabled:opacity-40"
              onClick={() => void addRule()}
            >
              Validate &amp; add rule
            </button>
          </div>
        </div>

        <footer className="shrink-0 border-t border-white/10 px-4 py-3 sm:px-5">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg border border-white/15 py-2 text-sm text-white/80 hover:bg-white/5"
          >
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}
