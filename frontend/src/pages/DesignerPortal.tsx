import { motion, AnimatePresence } from "framer-motion";
import {
  KeyboardEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
} from "react";
import { createPortal } from "react-dom";
import ChatMessageView from "../components/designer/ChatMessageView";
import DesignerAgentProgress, { designerAgentPhaseCount } from "../components/designer/DesignerAgentProgress";
import ConfirmDialog from "../components/designer/ConfirmDialog";
import MediaLibraryDrawer from "../components/designer/MediaLibraryDrawer";
import TemplateLibraryCard from "../components/designer/TemplateLibraryCard";
import ShortcutHelpModal from "../components/designer/ShortcutHelpModal";
import StudioPortalBootSplash from "../components/designer/StudioPortalBootSplash";
import StudioPortalLogin from "../components/designer/StudioPortalLogin";
import StudioSnackbar, { inferSnackbarTone, type SnackbarTone } from "../components/designer/StudioSnackbar";
import TemplateIconButton, {
  IconCheckTemplate,
  IconClearChat,
  IconDuplicate,
  IconExport,
  IconExternalTab,
  IconFullscreen,
  IconHelp,
  IconMediaLibrary,
  IconMonitor,
  IconPhoneDevice,
  IconRegenerate,
  IconSampleData,
  IconSave,
  IconSendArrow,
  IconStar,
  IconPaperclip,
  IconMic,
  IconTabletDevice,
  IconTrash,
  IconUndo,
} from "../components/designer/TemplateIconButton";
import { IconNavMap } from "../components/AppNavIcons";
import {
  designerChat,
  deleteTemplate,
  downloadJson,
  duplicateTemplate,
  exportTemplateBundle,
  injectDefaultVenueMapIntoTemplate,
  listMediaAssets,
  listTemplates,
  loginDesigner,
  previewTemplate,
  restoreRevision,
  saveTemplate,
  updateTemplate,
  validateTemplate,
  type ChatMessage,
  type DesignerMediaAsset,
  type ProposalTemplate,
  type TemplateRevision,
} from "../lib/designerApi";
import { uploadDesignerAssetWithProgress } from "../lib/designerUpload";
import { compileLocalTemplatePreview } from "../lib/designerTemplatePreview";
import {
  readLastDesignerTemplateId,
  writeLastDesignerTemplateId,
} from "../lib/studioLastSelection";
import { useStudioPortalAuth } from "../hooks/useStudioPortalAuth";
import { useAppShell } from "../context/AppShellContext";

const ACCEPT = "image/*,video/*";
const COMPOSER_MAX_LINES = 4;
const SUGGESTED_PROMPTS = [
  "Luxury dark theme with gold accents and hero video",
  "Corporate clean layout with sticky pricing summary",
  "Embed uploaded media in a responsive gallery grid",
  "Add the system default venue map at {{selected_map_svg}} with a responsive iframe slot",
];

type TemplateSnapshot = { html: string; css: string; js: string };
type UploadRow = { id: string; name: string; progress: number; status: "uploading" | "done" | "error" };

type SnackbarState = { message: string; tone: SnackbarTone };

export default function DesignerPortal() {
  const { theme } = useAppShell();
  const { authed, bootstrapping, confirmSession } = useStudioPortalAuth("designer");
  const [email, setEmail] = useState("designer@demo.local");
  const [password, setPassword] = useState("demo12345");
  const [templates, setTemplates] = useState<ProposalTemplate[]>([]);
  const [templateSearch, setTemplateSearch] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [name, setName] = useState("Untitled theme");
  const [revisions, setRevisions] = useState<TemplateRevision[]>([]);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [html, setHtml] = useState("");
  const [css, setCss] = useState("");
  const [js, setJs] = useState("");
  const [draft, setDraft] = useState("");
  const [previewDoc, setPreviewDoc] = useState("");
  const [busy, setBusy] = useState(false);
  const [agentPhaseIndex, setAgentPhaseIndex] = useState(0);
  const [snackbar, setSnackbar] = useState<SnackbarState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);
  const [showSampleData, setShowSampleData] = useState(true);
  const [attachments, setAttachments] = useState<DesignerMediaAsset[]>([]);
  const [libraryAssets, setLibraryAssets] = useState<DesignerMediaAsset[]>([]);
  const [uploadRows, setUploadRows] = useState<UploadRow[]>([]);
  const uploading = uploadRows.some((u) => u.status === "uploading");
  const [dragActive, setDragActive] = useState(false);
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [undoStack, setUndoStack] = useState<TemplateSnapshot[]>([]);
  const [pinnedIdx, setPinnedIdx] = useState<Set<number>>(new Set());
  const [previewWidth, setPreviewWidth] = useState<"full" | "tablet" | "mobile">("full");
  const [previewFullscreen, setPreviewFullscreen] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [srStatus, setSrStatus] = useState("");
  const lastUserMessage = useRef("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const restoredSelectionRef = useRef(false);

  const filteredTemplates = useMemo(
    () =>
      templates.filter((t) =>
        t.name.toLowerCase().includes(templateSearch.trim().toLowerCase())
      ),
    [templates, templateSearch]
  );

  const activeTemplateIsDefault = useMemo(
    () => Boolean(templates.find((t) => t.id === activeId)?.is_default),
    [templates, activeId]
  );

  const previewFrameWidth =
    previewWidth === "tablet" ? "768px" : previewWidth === "mobile" ? "390px" : "100%";

  const showSnackbar = useCallback((message: string, tone?: SnackbarTone) => {
    setSnackbar({ message, tone: tone ?? inferSnackbarTone(message) });
  }, []);

  const dismissSnackbar = useCallback(() => setSnackbar(null), []);

  useEffect(() => {
    if (!busy) {
      setAgentPhaseIndex(0);
      return;
    }
    const id = window.setInterval(() => {
      setAgentPhaseIndex((i) => (i + 1) % designerAgentPhaseCount());
    }, 2200);
    return () => window.clearInterval(id);
  }, [busy]);

  const agentWorkingPreviewDoc = useMemo(
    () => compileLocalTemplatePreview(html, css, js),
    [html, css, js]
  );

  const syncComposerTextareaHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    const styles = window.getComputedStyle(el);
    const lineHeight = parseFloat(styles.lineHeight) || 20;
    const paddingY = parseFloat(styles.paddingTop) + parseFloat(styles.paddingBottom);
    const maxHeight = Math.ceil(lineHeight * COMPOSER_MAX_LINES + paddingY);
    const contentHeight = el.scrollHeight;
    const nextHeight = Math.min(contentHeight, maxHeight);
    el.style.height = `${nextHeight}px`;
    const scrollable = contentHeight > maxHeight;
    el.classList.toggle("studio-composer-input--scroll", scrollable);
  }, []);

  const refreshTemplates = useCallback(async () => {
    setTemplates(await listTemplates());
  }, []);

  const refreshLibrary = useCallback(async () => {
    setLibraryAssets(await listMediaAssets(activeId));
  }, [activeId]);

  useEffect(() => {
    if (!authed) {
      restoredSelectionRef.current = false;
      return;
    }
    let cancelled = false;
    void (async () => {
      const list = await listTemplates().catch(() => [] as ProposalTemplate[]);
      if (cancelled) return;
      setTemplates(list);
      if (restoredSelectionRef.current) return;
      const storedId = readLastDesignerTemplateId();
      if (storedId) {
        const match = list.find((t) => t.id === storedId);
        if (match) {
          setActiveId(match.id);
          setName(match.name);
          setHtml(match.html_markup);
          setCss(match.css_stylesheet);
          setJs(match.js_script || "");
          setHistory(match.chat_history_json || []);
          setRevisions(match.revision_history_json || []);
          setAttachments([]);
          setClarifications([]);
        } else {
          writeLastDesignerTemplateId(null);
        }
      }
      restoredSelectionRef.current = true;
    })();
    return () => {
      cancelled = true;
    };
  }, [authed]);

  useEffect(() => {
    if (authed) {
      refreshLibrary().catch(() => setLibraryAssets([]));
    }
  }, [authed, activeId, refreshLibrary]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, busy]);

  useLayoutEffect(() => {
    syncComposerTextareaHeight();
  }, [draft, syncComposerTextareaHeight]);

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "?" && !e.ctrlKey && !e.metaKey) {
        const t = e.target as HTMLElement;
        if (t.tagName !== "INPUT" && t.tagName !== "TEXTAREA") {
          e.preventDefault();
          setShowHelp(true);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!previewFullscreen) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") setPreviewFullscreen(false);
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [previewFullscreen]);

  const pushUndo = useCallback(() => {
    setUndoStack((s) => [...s.slice(-9), { html, css, js }]);
  }, [html, css, js]);

  const applyTemplate = (t: ProposalTemplate) => {
    writeLastDesignerTemplateId(t.id);
    setActiveId(t.id);
    setName(t.name);
    setHtml(t.html_markup);
    setCss(t.css_stylesheet);
    setJs(t.js_script || "");
    setHistory(t.chat_history_json || []);
    setRevisions(t.revision_history_json || []);
    setAttachments([]);
    setClarifications([]);
    dismissSnackbar();
  };

  const clearConversation = async () => {
    setHistory([]);
    setPinnedIdx(new Set());
    setConfirmClear(false);
    if (!activeId) return;
    try {
      await updateTemplate(activeId, { chat_history_json: [] });
      setTemplates((list) =>
        list.map((t) => (t.id === activeId ? { ...t, chat_history_json: [] } : t)),
      );
      showSnackbar("Conversation cleared.", "success");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not clear chat.";
      showSnackbar(msg, "error");
      await refreshTemplates();
    }
  };

  const newTemplate = () => {
    writeLastDesignerTemplateId(null);
    setActiveId(null);
    setName("Untitled theme");
    setHtml("");
    setCss("");
    setJs("");
    setHistory([]);
    setRevisions([]);
    setAttachments([]);
    dismissSnackbar();
  };

  const runValidate = async () => {
    setBusy(true);
    try {
      const result = await validateTemplate(html, css, js);
      const message = result.valid
        ? `Valid — ${result.summary}`
        : `Issues: ${(result.issues || []).join("; ")}`;
      showSnackbar(message, result.valid ? "success" : "warning");
      setSrStatus(result.valid ? "Validation passed." : "Validation found issues.");
    } catch {
      showSnackbar("Template check failed. Try again.", "error");
    } finally {
      setBusy(false);
    }
  };

  const refreshPreview = useCallback(async () => {
    if (!html && !css && !js) {
      setPreviewDoc("");
      return;
    }
    if (showSampleData) {
      const data = await previewTemplate(html, css, js);
      setPreviewDoc(data.compiled_html || "");
    } else {
      const style = css ? `<style>${css}</style>` : "";
      const script = js ? `<script>${js}</script>` : "";
      setPreviewDoc(
        `<!DOCTYPE html><html><head><meta charset='utf-8'><style>html,body{font-family:system-ui,sans-serif;margin:0;}</style>${style}</head><body>${html}${script}</body></html>`
      );
    }
  }, [css, html, js, showSampleData]);

  const insertDefaultVenueMapSlot = useCallback(async () => {
    setBusy(true);
    try {
      const updated = await injectDefaultVenueMapIntoTemplate(html, css);
      setHtml(updated.html_markup);
      setCss(updated.css_stylesheet);
      if (!updated.default_map.available) {
        showSnackbar(updated.default_map.detail || "No default map in Map Studio.", "warning");
      } else {
        showSnackbar(`Inserted map slot — ${updated.default_map.title || "default map"}`, "success");
        setSrStatus("Default venue map slot added. Turn on sample data in preview to see the live map.");
      }
      await refreshPreview();
    } catch {
      showSnackbar("Could not insert default venue map slot.", "error");
    } finally {
      setBusy(false);
    }
  }, [css, html, refreshPreview, showSnackbar]);

  useEffect(() => {
    refreshPreview().catch(() => setPreviewDoc(""));
  }, [refreshPreview]);

  const uploadFiles = async (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      const rowId = `${file.name}-${Date.now()}`;
      setUploadRows((r) => [...r, { id: rowId, name: file.name, progress: 0, status: "uploading" }]);
      try {
        const asset = await uploadDesignerAssetWithProgress(file, activeId, (pct) => {
          setUploadRows((rows) =>
            rows.map((x) => (x.id === rowId ? { ...x, progress: pct } : x))
          );
        });
        setUploadRows((rows) =>
          rows.map((x) => (x.id === rowId ? { ...x, progress: 100, status: "done" } : x))
        );
        setAttachments((p) => [...p, asset]);
        setLibraryAssets((p) => [asset, ...p]);
        setSrStatus(`Uploaded ${file.name}`);
      } catch (err) {
        setUploadRows((rows) =>
          rows.map((x) => (x.id === rowId ? { ...x, status: "error" } : x))
        );
        setError(err instanceof Error ? err.message : "Upload failed");
      }
    }
    setTimeout(() => setUploadRows((r) => r.filter((x) => x.status === "uploading")), 3000);
  };

  const sendMessage = async (textOverride?: string) => {
    const text = (textOverride ?? draft).trim();
    if ((!text && attachments.length === 0) || busy) return;
    lastUserMessage.current = text;
    pushUndo();
    setBusy(true);
    setError(null);
    setClarifications([]);
    const pendingUser: ChatMessage = {
      role: "user",
      content: text || "(attachments only)",
      ts: new Date().toISOString(),
    };
    setHistory((h) => [...h, pendingUser]);
    setDraft("");
    const pendingAttachments = [...attachments];
    setAttachments([]);
    try {
      const data = await designerChat({
        message: text,
        history: history,
        html_markup: html,
        css_stylesheet: css,
        js_script: js,
        attachment_ids: pendingAttachments.map((a) => a.id),
        template_id: activeId || undefined,
      });
      setHistory(data.history || []);
      setHtml(data.html_markup || html);
      setCss(data.css_stylesheet || css);
      setJs(data.js_script || js);
      setClarifications(data.clarification_options || []);
      dismissSnackbar();
      setSrStatus("Agent updated the proposal template.");
    } catch {
      setError("Design agent request failed.");
      setHistory((h) => h.filter((m) => m !== pendingUser));
      setAttachments(pendingAttachments);
    } finally {
      setBusy(false);
    }
  };

  const regenerate = () => {
    if (lastUserMessage.current) void sendMessage(lastUserMessage.current);
  };

  const undo = () => {
    setUndoStack((stack) => {
      const prev = stack[stack.length - 1];
      if (!prev) return stack;
      setHtml(prev.html);
      setCss(prev.css);
      setJs(prev.js);
      setSrStatus("Reverted last template change.");
      return stack.slice(0, -1);
    });
  };

  const handleExport = async () => {
    const bundle = {
      exported_at: new Date().toISOString(),
      name,
      html_markup: html,
      css_stylesheet: css,
      js_script: js,
      chat_history_json: history,
    };
    if (activeId) {
      try {
        const server = await exportTemplateBundle(activeId);
        downloadJson(`${name.replace(/\s+/g, "_")}_export.json`, server);
        return;
      } catch {
        /* fall through */
      }
    }
    downloadJson(`${name.replace(/\s+/g, "_")}_export.json`, bundle);
  };

  const openPreviewTab = () => {
    if (!previewDoc) return;
    const blob = new Blob([previewDoc], { type: "text/html" });
    window.open(URL.createObjectURL(blob), "_blank");
  };

  const startVoice = () => {
    type SpeechRecognitionCtor = new () => {
      lang: string;
      onresult: ((ev: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null;
      start: () => void;
    };
    const Rec = (window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }).SpeechRecognition
      || (window as unknown as { webkitSpeechRecognition?: SpeechRecognitionCtor }).webkitSpeechRecognition;
    if (!Rec) {
      setError("Voice input is not supported in this browser.");
      return;
    }
    const rec = new Rec();
    rec.lang = "en-US";
    rec.onresult = (ev) => {
      const t = ev.results[0][0].transcript;
      setDraft((d) => (d ? `${d} ${t}` : t));
    };
    rec.start();
  };

  const insertMention = (asset: DesignerMediaAsset) => {
    setDraft((d) => `${d}${d ? " " : ""}@${asset.original_name} `);
    if (!attachments.find((a) => a.id === asset.id)) {
      setAttachments((p) => [...p, asset]);
    }
    setMentionOpen(false);
    textareaRef.current?.focus();
  };

  const onComposerKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "@") setMentionOpen(true);
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  const mentionSuggestions = libraryAssets.filter((a) =>
    draft.includes("@")
      ? a.original_name.toLowerCase().includes(draft.split("@").pop()?.toLowerCase() || "")
      : true
  );

  const shellClass =
    theme === "light"
      ? "designer-shell-light flex h-full min-h-0 flex-col overflow-hidden"
      : "flex h-full min-h-0 flex-col overflow-hidden text-white";

  if (bootstrapping && !authed) {
    return (
      <div className={`${shellClass} items-center justify-center`}>
        <StudioPortalBootSplash title="Designing Studio" />
      </div>
    );
  }

  if (!authed) {
    const runLogin = async (userEmail: string, userPassword: string) => {
      setLoginBusy(true);
      setError(null);
      try {
        const session = await loginDesigner(userEmail, userPassword);
        const ok = await confirmSession(session);
        if (!ok) {
          setError("Signed in but session was not saved. Allow cookies for this site and try again.");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Login failed.");
      } finally {
        setLoginBusy(false);
      }
    };

    return (
      <div className={`${shellClass} min-h-0 flex-1`}>
        <StudioPortalLogin
          title="Designing Studio"
          subtitle="Build proposal templates with the design agent"
          error={error}
          email={email}
          password={password}
          busy={loginBusy}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onSubmit={() => runLogin(email, password)}
          onMockSso={async () => {
            const demoEmail = "designer@demo.local";
            const demoPass = "demo12345";
            setEmail(demoEmail);
            setPassword(demoPass);
            await runLogin(demoEmail, demoPass);
          }}
        />
      </div>
    );
  }

  const renderPreviewToolbar = () => (
    <div className="studio-preview-toolbar" role="toolbar" aria-label="Preview controls">
      {(
        [
          { id: "full" as const, label: "Full width preview", icon: <IconMonitor /> },
          { id: "tablet" as const, label: "Tablet preview", icon: <IconTabletDevice /> },
          { id: "mobile" as const, label: "Mobile preview", icon: <IconPhoneDevice /> },
        ] as const
      ).map(({ id, label, icon }) => (
        <TemplateIconButton
          key={id}
          compact
          label={label}
          selected={previewWidth === id}
          onClick={() => setPreviewWidth(id)}
        >
          {icon}
        </TemplateIconButton>
      ))}
      <span className="studio-preview-toolbar-divider" aria-hidden />
      <TemplateIconButton compact label="Open preview in new tab" onClick={openPreviewTab}>
        <IconExternalTab />
      </TemplateIconButton>
      <TemplateIconButton
        compact
        label={previewFullscreen ? "Exit fullscreen" : "Fullscreen preview"}
        selected={previewFullscreen}
        onClick={() => setPreviewFullscreen((v) => !v)}
      >
        <IconFullscreen exit={previewFullscreen} />
      </TemplateIconButton>
      <span className="studio-preview-toolbar-divider" aria-hidden />
      <TemplateIconButton
        compact
        label={showSampleData ? "Sample RFP data on" : "Sample RFP data off"}
        selected={showSampleData}
        onClick={() => setShowSampleData((v) => !v)}
      >
        <IconSampleData />
      </TemplateIconButton>
      <TemplateIconButton
        compact
        label="Check template"
        variant="primary"
        disabled={busy || !html}
        onClick={() => void runValidate()}
      >
        <IconCheckTemplate />
      </TemplateIconButton>
    </div>
  );

  const renderLivePreview = (mode: "inline" | "fullscreen") => {
    const fullscreen = mode === "fullscreen";
    return (
      <section
        className={
          fullscreen
            ? "fixed inset-0 z-[300] flex h-dvh w-dvw min-h-0 flex-col overflow-hidden bg-[#0a0f1a]"
            : "flex min-h-0 min-w-0 flex-[1.05] flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04]"
        }
      >
        <header
          className={`shrink-0 border-b border-white/10 ${fullscreen ? "bg-[#0a0f1a]/98 px-4 py-3" : ""}`}
        >
          <div
            className={`flex flex-wrap items-center justify-between gap-3 ${fullscreen ? "" : "px-[var(--studio-inset-x)] pb-4 pt-5"}`}
          >
            <div className="flex min-w-0 flex-wrap items-center gap-3">
              <h2 className="text-lg font-semibold">Live preview</h2>
              {fullscreen && (
                <button
                  type="button"
                  onClick={() => setPreviewFullscreen(false)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-violet-400/40 bg-violet-600/30 px-3 py-1.5 text-xs font-semibold text-violet-100 transition hover:bg-violet-600/50"
                >
                  <IconFullscreen exit />
                  Exit fullscreen
                </button>
              )}
            </div>
            {renderPreviewToolbar()}
          </div>
        </header>
        <div className={`relative min-h-0 flex-1 bg-[#1a1a1f] ${fullscreen ? "p-2 sm:p-3" : "p-4"}`}>
          <div className="mx-auto flex h-full min-h-0 justify-center">
            <div
              className={`relative h-full min-h-0 overflow-hidden border border-white/10 bg-[#ececef] shadow-inner transition-all ${
                fullscreen && previewWidth === "full" ? "w-full rounded-none" : "rounded-xl"
              }`}
              style={{
                width: fullscreen && previewWidth === "full" ? "100%" : previewFrameWidth,
                maxWidth: "100%",
              }}
            >
              {previewDoc ? (
                <iframe
                  title="Proposal preview"
                  className="absolute inset-0 h-full w-full border-0 bg-white"
                  sandbox="allow-scripts allow-same-origin"
                  srcDoc={previewDoc}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">
                  No preview yet
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    );
  };

  const previewPanel = renderLivePreview("inline");
  const fullscreenPreviewPortal =
    previewFullscreen && typeof document !== "undefined"
      ? createPortal(renderLivePreview("fullscreen"), document.body)
      : null;

  return (
    <div className={shellClass}>
      <div aria-live="polite" className="sr-only">
        {srStatus}
      </div>
      <StudioSnackbar
        open={Boolean(snackbar?.message)}
        message={snackbar?.message ?? ""}
        tone={snackbar?.tone}
        onClose={dismissSnackbar}
      />
      <ShortcutHelpModal open={showHelp} onClose={() => setShowHelp(false)} />
      <MediaLibraryDrawer open={showLibrary} assets={libraryAssets} onClose={() => setShowLibrary(false)} onAttach={(a) => setAttachments((p) => (p.find((x) => x.id === a.id) ? p : [...p, a]))} onInsertMention={insertMention} />
      <ConfirmDialog open={confirmClear} title="Clear conversation?" message="This permanently clears the design agent chat for this template." onCancel={() => setConfirmClear(false)} onConfirm={() => void clearConversation()} />
      <ConfirmDialog open={confirmDelete} title="Delete template?" message="This permanently removes the template from your library." confirmLabel="Delete" onCancel={() => setConfirmDelete(false)} onConfirm={async () => { if (activeId) { await deleteTemplate(activeId); setActiveId(null); newTemplate(); await refreshTemplates(); } setConfirmDelete(false); }} />

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden px-4 pb-[var(--studio-safe-bottom)] pt-3 sm:flex-row sm:px-6">
        <aside className="flex max-h-[32vh] w-full shrink-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] sm:max-h-none sm:w-64">
          <div className="studio-panel-header !min-h-[4rem]">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-white/45">Library</p>
              <h2 className="font-semibold">Templates</h2>
            </div>
            <button type="button" onClick={newTemplate} className="studio-btn-secondary !min-h-0 px-2.5 py-1.5 text-[11px]">+ New</button>
          </div>
          <div className="studio-panel-body !pb-2">
            <label className="mb-1.5 block text-[10px] font-medium uppercase tracking-wide text-white/40">Search templates</label>
            <div className="relative">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-white/35" aria-hidden>
                ⌕
              </span>
              <input
                placeholder="Search by name…"
                value={templateSearch}
                onChange={(e) => setTemplateSearch(e.target.value)}
                className="studio-field !py-2 !pl-8 text-xs"
              />
            </div>
          </div>
          <ul className="studio-scroll min-h-0 flex-1 space-y-2.5 overflow-y-auto px-[var(--studio-inset-x)] pb-2">
            {filteredTemplates.map((t) => (
              <li key={t.id}>
                <TemplateLibraryCard
                  template={t}
                  selected={activeId === t.id}
                  onSelect={() => applyTemplate(t)}
                />
              </li>
            ))}
            {filteredTemplates.length === 0 && (
              <li className="rounded-xl border border-dashed border-white/15 px-3 py-6 text-center text-xs text-white/40">
                No templates match your search.
              </li>
            )}
          </ul>
          {revisions.length > 0 && (
            <div className="border-t border-white/10 px-[var(--studio-inset-x)] py-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-white/40">Version history</p>
              <ul className="studio-scroll mt-2 max-h-24 space-y-1 overflow-y-auto">
                {revisions.map((rev, idx) => (
                  <li key={rev.saved_at + idx}>
                    <button type="button" className="w-full text-left text-[10px] text-violet-200 hover:underline" onClick={async () => { if (!activeId) return; const t = await restoreRevision(activeId, idx); applyTemplate(t); }}>
                      {new Date(rev.saved_at).toLocaleString()} — {rev.note}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="studio-panel-footer space-y-3">
            <div>
              <label className="mb-1.5 block text-[10px] font-medium uppercase tracking-wide text-white/40">Template name</label>
              <input className="studio-field" value={name} onChange={(e) => setName(e.target.value)} aria-label="Template name" />
            </div>
            <div className="studio-template-actions">
              <TemplateIconButton
                label="Duplicate template"
                disabled={!activeId || busy}
                onClick={async () => {
                  if (activeId) {
                    const c = await duplicateTemplate(activeId);
                    await refreshTemplates();
                    applyTemplate(c);
                  }
                }}
              >
                <IconDuplicate />
              </TemplateIconButton>
              <TemplateIconButton
                label="Delete template"
                variant="danger"
                disabled={!activeId || busy}
                onClick={() => setConfirmDelete(true)}
              >
                <IconTrash />
              </TemplateIconButton>
              <TemplateIconButton
                label="Save template"
                variant="primary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const payload = {
                      name,
                      html_markup: html,
                      css_stylesheet: css,
                      js_script: js,
                      chat_history_json: history,
                      is_default: false,
                    };
                    if (activeId) await updateTemplate(activeId, payload);
                    else {
                      const c = await saveTemplate(payload);
                      setActiveId(c.id);
                      applyTemplate(c);
                    }
                    await refreshTemplates();
                    showSnackbar("Template saved successfully.", "success");
                  } catch (e) {
                    const msg = e instanceof Error ? e.message : "Save failed";
                    showSnackbar(msg, "error");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <IconSave />
              </TemplateIconButton>
              <TemplateIconButton
                label={activeTemplateIsDefault ? "Default template" : "Set as default"}
                variant="accent"
                active={activeTemplateIsDefault}
                disabled={!activeId || busy}
                onClick={() => {
                  if (activeId) void updateTemplate(activeId, { is_default: true }).then(refreshTemplates);
                }}
              >
                <IconStar filled={activeTemplateIsDefault} />
              </TemplateIconButton>
              <TemplateIconButton label="Export JSON" disabled={busy} onClick={() => void handleExport()}>
                <IconExport />
              </TemplateIconButton>
            </div>
          </div>
        </aside>

        <section className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]" onDragOver={(e) => { e.preventDefault(); setDragActive(true); }} onDragLeave={() => setDragActive(false)} onDrop={async (e: DragEvent) => { e.preventDefault(); setDragActive(false); if (e.dataTransfer.files?.length) await uploadFiles(e.dataTransfer.files); }}>
          <AnimatePresence>
            {dragActive && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="pointer-events-none absolute inset-3 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-violet-300 bg-violet-600/25">
                <p className="text-lg font-semibold">Release to upload</p>
              </motion.div>
            )}
          </AnimatePresence>
          <header className="studio-panel-header">
            <div>
              <h2 className="text-lg font-semibold">Design Agent</h2>
              <p className="text-xs text-white/50">Drop media · Enter to send · Shift+Enter newline</p>
            </div>
            <div className="studio-toolbar">
              <TemplateIconButton compact label="Keyboard shortcuts" onClick={() => setShowHelp(true)}>
                <IconHelp />
              </TemplateIconButton>
              <TemplateIconButton compact label="Media library" onClick={() => setShowLibrary(true)}>
                <IconMediaLibrary />
              </TemplateIconButton>
              <TemplateIconButton
                compact
                label="Regenerate last response"
                disabled={!lastUserMessage.current || busy}
                onClick={regenerate}
              >
                <IconRegenerate />
              </TemplateIconButton>
              <TemplateIconButton compact label="Undo layout" disabled={undoStack.length === 0} onClick={undo}>
                <IconUndo />
              </TemplateIconButton>
              <TemplateIconButton compact label="Clear chat" variant="danger" onClick={() => setConfirmClear(true)}>
                <IconClearChat />
              </TemplateIconButton>
            </div>
          </header>
          <div className="studio-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-[var(--studio-inset-x)] py-4">
            {history.length === 0 && (
              <div className="rounded-xl border border-white/10 bg-black/25 p-4 text-sm text-white/65">
                <p className="font-medium text-white/85">Start designing</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUGGESTED_PROMPTS.map((p) => (
                    <button key={p} type="button" className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-violet-500/10" onClick={() => void sendMessage(p)} disabled={busy}>{p}</button>
                  ))}
                </div>
              </div>
            )}
            {history.map((msg, i) => (
              <ChatMessageView key={`${msg.role}-${i}-${msg.ts}`} msg={msg} pinned={pinnedIdx.has(i)} onTogglePin={() => setPinnedIdx((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; })} />
            ))}
            {clarifications.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {clarifications.map((c) => (
                  <button key={c} type="button" className="rounded-full bg-fuchsia-600/30 px-3 py-1 text-xs hover:bg-fuchsia-600/50" onClick={() => void sendMessage(c)}>{c}</button>
                ))}
              </div>
            )}
            <DesignerAgentProgress
              active={busy}
              phaseIndex={agentPhaseIndex}
              previewDoc={agentWorkingPreviewDoc}
            />
            <div ref={chatEndRef} />
          </div>
          {uploadRows.length > 0 && (
            <div className="space-y-1 px-[var(--studio-inset-x)] pb-2">
              {uploadRows.map((u) => (
                <div key={u.id} className="text-[10px] text-white/50">
                  {u.name} — {u.status === "uploading" ? `${u.progress}%` : u.status}
                  {u.status === "uploading" && <div className="mt-0.5 h-1 rounded bg-white/10"><div className="h-1 rounded bg-violet-500 transition-all" style={{ width: `${u.progress}%` }} /></div>}
                </div>
              ))}
            </div>
          )}
          {!dragActive && attachments.length === 0 && (
            <div className="mx-[var(--studio-inset-x)] mb-2 flex items-center justify-center gap-2 rounded-xl border border-dashed border-violet-400/25 bg-violet-500/[0.06] px-3 py-3 text-center text-[11px] text-white/50">
              <span aria-hidden>⬆</span>
              Drag & drop images or videos here
            </div>
          )}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 px-[var(--studio-inset-x)] pb-2">
              {attachments.map((a) => (
                <div key={a.id} className="flex items-center gap-2 rounded-xl border border-white/15 bg-black/35 px-2 py-1 text-xs">
                  {a.media_type === "VIDEO" ? <video src={a.url} className="h-11 w-16 rounded-md object-cover" muted /> : <img src={a.url} alt="" className="h-11 w-16 rounded-md object-cover" />}
                  <span className="max-w-[90px] truncate">{a.original_name}</span>
                  <button type="button" onClick={() => setAttachments((p) => p.filter((x) => x.id !== a.id))}>×</button>
                </div>
              ))}
            </div>
          )}
          {mentionOpen && mentionSuggestions.length > 0 && (
            <ul className="studio-scroll mx-[var(--studio-inset-x)] mb-2 max-h-32 overflow-y-auto rounded-xl border border-white/15 bg-[#0c1220]">
              {mentionSuggestions.slice(0, 8).map((a) => (
                <li key={a.id}><button type="button" className="w-full px-3 py-2 text-left text-xs hover:bg-white/5" onClick={() => insertMention(a)}>{a.original_name}</button></li>
              ))}
            </ul>
          )}
          {error && <p className="border-t border-red-500/20 bg-red-950/30 px-[var(--studio-inset-x)] py-2 text-sm text-red-300">{error}</p>}
          <form onSubmit={(e) => { e.preventDefault(); void sendMessage(); }} className="studio-composer">
            <div className="studio-composer-unified">
              <div className="studio-composer-row">
                <div className="studio-composer-icons">
                  <motion.button
                    type="button"
                    className="studio-composer-action"
                    aria-label="Attach files"
                    title="Attach files"
                    onClick={() => fileInputRef.current?.click()}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    transition={{ type: "spring", stiffness: 520, damping: 28 }}
                  >
                    <IconPaperclip />
                  </motion.button>
                  <motion.button
                    type="button"
                    className="studio-composer-action"
                    aria-label="Insert default venue map slot"
                    title="Insert default venue map ({{selected_map_svg}})"
                    disabled={busy}
                    onClick={() => void insertDefaultVenueMapSlot()}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    transition={{ type: "spring", stiffness: 520, damping: 28 }}
                  >
                    <IconNavMap />
                  </motion.button>
                  <motion.button
                    type="button"
                    className="studio-composer-action"
                    aria-label="Voice input"
                    title="Voice input"
                    onClick={startVoice}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    transition={{ type: "spring", stiffness: 520, damping: 28 }}
                  >
                    <IconMic />
                  </motion.button>
                </div>
                <input ref={fileInputRef} type="file" accept={ACCEPT} multiple className="hidden" onChange={(e) => e.target.files && uploadFiles(e.target.files)} />
                <textarea
                  ref={textareaRef}
                  rows={1}
                  className="studio-composer-input"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onInput={syncComposerTextareaHeight}
                  onKeyDown={onComposerKeyDown}
                  placeholder="Message the design agent… @ to mention an asset"
                  disabled={busy}
                  aria-label="Message to design agent"
                />
                <motion.button
                  type="submit"
                  disabled={busy || uploading}
                  className="studio-composer-send"
                  aria-label="Send message"
                  title="Send"
                  whileHover={busy || uploading ? undefined : { scale: 1.03 }}
                  whileTap={busy || uploading ? undefined : { scale: 0.97 }}
                  transition={{ type: "spring", stiffness: 520, damping: 28 }}
                >
                  <IconSendArrow />
                </motion.button>
              </div>
              <p className="studio-composer-hint">Enter to send · Shift+Enter for a new line</p>
            </div>
          </form>
        </section>

        {!previewFullscreen && previewPanel}
        {fullscreenPreviewPortal}
      </div>
    </div>
  );
}
