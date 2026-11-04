import { useCallback, useEffect, useState } from "react";
import { useAppShell } from "../../context/AppShellContext";
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
    <div className="studio-agent-rules-empty" role="status">
      <div className="studio-agent-rules-empty-icon" aria-hidden>
        <IconAgentRules size={28} />
      </div>
      <p className="studio-agent-rules-empty-title">No agent rules yet</p>
      <p className="studio-agent-rules-empty-body">
        Add plain-language instructions for layout, tone, dates, CTAs, and brand guardrails. The design agent pulls the
        most relevant rules on every turn.
      </p>
      <ul className="studio-agent-rules-empty-list">
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
      <p className="studio-agent-rules-empty-kicker">Start with the field below</p>
    </div>
  );
}

function AgentRulesLoadingState() {
  return (
    <div className="studio-agent-rules-loading" role="status" aria-live="polite">
      <div className="studio-agent-rules-loading-icon">
        <IconAgentRules size={28} />
      </div>
      <p className="studio-agent-rules-loading-text">Loading your rules…</p>
    </div>
  );
}

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function AgentRulesDialog({ open, onClose }: Props) {
  const { theme } = useAppShell();
  const light = theme === "light";
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

  const panelClass = ["studio-dialog-panel", light ? "designer-shell-light" : ""].filter(Boolean).join(" ");

  return (
    <div
      className="studio-dialog-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-rules-title"
      onClick={onClose}
    >
      <div className={panelClass} onClick={(e) => e.stopPropagation()}>
        <header className="studio-dialog-header">
          <h3 id="agent-rules-title" className="studio-dialog-title">
            Agent rules
          </h3>
          <p className="studio-dialog-subtitle">
            Plain-language instructions for the design agent. Retrieved by hybrid semantic + keyword match each turn.
          </p>
        </header>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            className={`studio-dialog-body space-y-3 ${
              loadState === "ready" && rules.length === 0 ? "flex flex-col justify-center" : ""
            }`}
          >
            {error && <p className="studio-dialog-error">{error}</p>}

            {conflict && (
              <div className="studio-dialog-conflict">
                <p className="studio-dialog-conflict-title">Rule conflict</p>
                <p className="studio-dialog-conflict-body">{conflict.explanation}</p>
                {conflict.suggested ? (
                  <p className="studio-dialog-conflict-suggest">{conflict.suggested}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2">
                  {conflict.suggested ? (
                    <>
                      <button
                        type="button"
                        className="rounded-lg bg-violet-600 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-violet-500"
                        onClick={() => void applySuggested()}
                      >
                        Use suggestion in draft
                      </button>
                      <button
                        type="button"
                        className="rounded-lg border border-violet-400/40 px-2.5 py-1 text-[11px] text-violet-100 hover:bg-violet-500/10"
                        onClick={() => void addSuggestedAsRule()}
                        disabled={busy}
                      >
                        Add suggestion to rules
                      </button>
                    </>
                  ) : null}
                  <button
                    type="button"
                    className="studio-dialog-conflict-dismiss"
                    onClick={() => setConflict(null)}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            <ul className="space-y-2">
              {rules.map((rule, idx) => (
                <li key={rule.id} className="studio-agent-rules-item">
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
                          className="rounded-lg bg-violet-600 px-2.5 py-1 text-[11px] font-medium text-white"
                          onClick={() => void saveEdit(rule)}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className="studio-btn-secondary !min-h-0 px-2.5 py-1 text-[11px]"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="studio-agent-rules-item-body">{rule.body}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
                        <button
                          type="button"
                          className="studio-agent-rules-edit"
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
                          className="studio-agent-rules-remove"
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
                        <span className="studio-agent-rules-item-index">#{idx + 1}</span>
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

          <div className="studio-dialog-compose">
            <label className="studio-dialog-label">New rule</label>
            <textarea
              className="studio-field min-h-[4.5rem] w-full text-xs sm:min-h-[5rem]"
              placeholder="e.g. Always keep the accept CTA visible on desktop and use MM/DD/YYYY for dates."
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <button
              type="button"
              disabled={busy || !draft.trim()}
              className="studio-login-primary mt-2 w-full text-xs"
              onClick={() => void addRule()}
            >
              Validate &amp; add rule
            </button>
          </div>
        </div>

        <footer className="studio-dialog-footer">
          <button type="button" onClick={onClose} className="studio-dialog-close-btn">
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}
