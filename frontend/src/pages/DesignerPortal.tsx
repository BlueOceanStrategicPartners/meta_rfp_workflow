import PreviewAutomationIndicator from "../components/designer/PreviewAutomationIndicator";
import PreviewTargetHighlight from "../components/designer/PreviewTargetHighlight";
import {
  runPreviewPanelAutomation,
  waitForPreviewIframe,
  shouldAttachPreviewAutomation,
} from "../lib/designerPreviewAutomation";
import {
  composeMessageWithPreviewTarget,
  type PreviewElementTarget,
} from "../lib/designerPreviewElementPicker";
import { previewTargetToAttachment } from "../lib/previewTargetChat";
import { usePreviewElementPicker } from "../hooks/usePreviewElementPicker";
import { motion, AnimatePresence } from "framer-motion";
import {
  KeyboardEvent,
  ClipboardEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
} from "react";
import { flushSync } from "react-dom";
import { createPortal } from "react-dom";
import ChatMessageView from "../components/designer/ChatMessageView";
import DesignerAgentProgress from "../components/designer/DesignerAgentProgress";
import {
  streamDesignerChat,
  normalizeAgentWorkPlanSteps,
  type AgentPreviewSnapshot,
  type AgentProgressItem,
  type AgentToolStep,
  type AgentWorkPlanStep,
} from "../lib/designerChatStream";
import {
  collapseCompletedExecutionTodos,
  isPlanningOnlyTodos,
  PLANNING_WAIT_TODOS,
} from "../lib/designerAgentTodos";
import { resolveAgentProgressUi } from "../lib/designerProgressState";
import {
  liveProgressSnapshotHasWork,
  shouldResumeBusyFromLiveProgress,
} from "../lib/designerLiveProgressSafety";
import ConfirmDialog from "../components/designer/ConfirmDialog";
import MediaLibraryDrawer from "../components/designer/MediaLibraryDrawer";
import AgentRulesDialog from "../components/designer/AgentRulesDialog";
import TemplateLibraryCard from "../components/designer/TemplateLibraryCard";
import TemplateVersionHistoryDialog from "../components/designer/TemplateVersionHistoryDialog";
import ShortcutHelpModal from "../components/designer/ShortcutHelpModal";
import StudioPortalBootSplash from "../components/designer/StudioPortalBootSplash";
import StudioPortalLogin from "../components/designer/StudioPortalLogin";
import StudioSnackbar, { inferSnackbarTone, type SnackbarTone } from "../components/designer/StudioSnackbar";
import TemplateIconButton, {
  IconAgentRules,
  IconCheckTemplate,
  IconClearChat,
  IconExternalTab,
  IconFullscreen,
  IconHelp,
  IconMediaLibrary,
  IconMonitor,
  IconPhoneDevice,
  IconRegenerate,
  IconSampleData,
  IconSendArrow,
  IconPaperclip,
  IconMic,
  IconTabletDevice,
  IconTargetPick,
  IconUndo,
} from "../components/designer/TemplateIconButton";
import {
  deleteTemplate,
  downloadJson,
  duplicateTemplate,
  exportTemplateBundle,
  fetchDesignerLiveProgress,
  cancelDesignerAgentSession,
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
  type PreviewAutomationReport,
  type ProposalTemplate,
  type TemplateRevision,
} from "../lib/designerApi";
import {
  imageFilesFromClipboardEvent,
  labelPastedScreenshotFile,
  uploadDesignerAssetWithProgress,
} from "../lib/designerUpload";
import { applyLivePreviewDocumentChrome, compileLocalTemplatePreview } from "../lib/designerTemplatePreview";
import { applyDesignerLiveProgressSnapshot } from "../lib/designerLiveProgressApply";
import {
  dismissLatestAssistantActionState,
  restoreDesignerActionUi,
} from "../lib/designerChatActionState";
import {
  readLastDesignerTemplateId,
  writeLastDesignerTemplateId,
} from "../lib/studioLastSelection";
import { useStudioPortalAuth } from "../hooks/useStudioPortalAuth";
import { useLivePreviewIframeScrollPort } from "../hooks/useLivePreviewIframeScrollPort";
import { useAppShell } from "../context/AppShellContext";

const ACCEPT = "image/*,video/*";
const COMPOSER_MAX_LINES = 10;
const SUGGESTED_PROMPTS = [
  "Corporate summit proposal with map slot — skip questions and build both stages",
  "Luxury dark theme with gold accents and hero video",
  "Create the proposal, then ask me for a floorplan to build the interactive map",
  "List my saved venue maps",
  "Embed uploaded media in a responsive gallery grid",
];

type TemplateSnapshot = { html: string; css: string; js: string };
type UploadRow = { id: string; name: string; progress: number; status: "uploading" | "done" | "error" };

type TemplatePersistSnapshot = {
  name: string;
  html: string;
  css: string;
  js: string;
  historyKey: string;
};

function buildPersistSnapshot(
  name: string,
  html: string,
  css: string,
  js: string,
  history: ChatMessage[],
): TemplatePersistSnapshot {
  const historyKey = JSON.stringify(
    history.map((m) => ({ role: m.role, content: m.content, ts: m.ts ?? "" })),
  );
  return {
    name,
    html,
    css,
    js: js || "",
    historyKey,
  };
}

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
  const [agentWorkPlan, setAgentWorkPlan] = useState<AgentWorkPlanStep[]>([]);
  const [agentTodos, setAgentTodos] = useState<AgentWorkPlanStep[]>([]);
  const [, setAgentToolSteps] = useState<AgentToolStep[]>([]);
  const [agentPartialProgress, setAgentPartialProgress] = useState<{
    completed: AgentProgressItem[];
    remaining: string[];
  } | null>(null);
  const agentToolStepsRef = useRef<AgentToolStep[]>([]);
  const agentTodosRef = useRef<AgentWorkPlanStep[]>([]);
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
  const [previewAutomationState, setPreviewAutomationState] = useState<
    "idle" | "running" | "used" | "error"
  >("idle");
  const [previewPickMode, setPreviewPickMode] = useState(false);
  const [previewElementTarget, setPreviewElementTarget] = useState<PreviewElementTarget | null>(
    null,
  );
  const [templateMenuOpenId, setTemplateMenuOpenId] = useState<string | null>(null);
  const [templateHistoryOpen, setTemplateHistoryOpen] = useState(false);
  const [showAgentRules, setShowAgentRules] = useState(false);
  const [savedSnapshot, setSavedSnapshot] = useState<TemplatePersistSnapshot | null>(null);
  const lastUserMessage = useRef("");
  const chatRunIdRef = useRef(0);
  const chatAbortRef = useRef<AbortController | null>(null);
  const previewIframeRef = useRef<HTMLIFrameElement>(null);
  const previewScrollRef = useRef<HTMLDivElement>(null);
  const previewPickShieldRef = useRef<HTMLDivElement>(null);
  const livePreviewIframeHeight = useLivePreviewIframeScrollPort(previewIframeRef, previewDoc);
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

  const templateIsDirty = useMemo(() => {
    const baseline = savedSnapshot;
    if (!baseline) {
      if (activeId) return false;
      return Boolean(html.trim() || css.trim() || js.trim() || history.length > 0 || name !== "Untitled theme");
    }
    const historyKey = JSON.stringify(
      history.map((m) => ({ role: m.role, content: m.content, ts: m.ts ?? "" })),
    );
    return (
      baseline.name !== name ||
      baseline.html !== html ||
      baseline.css !== css ||
      baseline.js !== (js || "") ||
      baseline.historyKey !== historyKey
    );
  }, [savedSnapshot, activeId, name, html, css, js, history]);

  const previewFrameWidth =
    previewWidth === "tablet" ? "768px" : previewWidth === "mobile" ? "390px" : "100%";

  const showSnackbar = useCallback((message: string, tone?: SnackbarTone) => {
    setSnackbar({ message, tone: tone ?? inferSnackbarTone(message) });
  }, []);

  const { hoverBox: previewHoverBox, lockedBox: previewLockedBox } = usePreviewElementPicker({
    iframeRef: previewIframeRef,
    scrollRef: previewScrollRef,
    shieldRef: previewPickShieldRef,
    active: previewPickMode && Boolean(previewDoc),
    lockedTarget: previewElementTarget,
    previewDoc,
    onSelect: (target) => {
      setPreviewElementTarget(target);
      setPreviewPickMode(false);
      showSnackbar("Section selected — describe what to change in the composer.", "success");
      window.requestAnimationFrame(() => textareaRef.current?.focus());
    },
  });

  const dismissSnackbar = useCallback(() => setSnackbar(null), []);

  const agentProgressUi = useMemo(
    () =>
      resolveAgentProgressUi({
        busy,
        agentTodos,
        agentPartialProgress,
      }),
    [busy, agentTodos, agentPartialProgress],
  );

  const agentWorkingPreviewDoc = useMemo(() => {
    if (!agentProgressUi.showProgressIframe) return "";
    return compileLocalTemplatePreview(html, css, js, { thumbnail: true });
  }, [agentProgressUi.showProgressIframe, html, css, js]);

  const PREVIEW_REFRESH_MIN_MS = 1200;
  const previewRefreshRef = useRef<{
    lastAt: number;
    pending: AgentPreviewSnapshot | null;
    timer: number;
  }>({ lastAt: 0, pending: null, timer: 0 });

  const flushAgentPreviewNow = useCallback((snap: AgentPreviewSnapshot) => {
    flushSync(() => {
      setHtml(snap.html_markup);
      setCss(snap.css_stylesheet);
      setJs(snap.js_script);
      setPreviewDoc(compileLocalTemplatePreview(snap.html_markup, snap.css_stylesheet, snap.js_script));
    });
    previewRefreshRef.current.lastAt = Date.now();
    previewRefreshRef.current.pending = null;
  }, []);

  const applyAgentPreviewSnapshot = useCallback(
    (snap: AgentPreviewSnapshot) => {
      const state = previewRefreshRef.current;
      const now = Date.now();
      if (now - state.lastAt >= PREVIEW_REFRESH_MIN_MS) {
        flushAgentPreviewNow(snap);
        return;
      }
      state.pending = snap;
      if (state.timer) return;
      const delay = Math.max(0, PREVIEW_REFRESH_MIN_MS - (now - state.lastAt));
      state.timer = window.setTimeout(() => {
        state.timer = 0;
        const pending = state.pending;
        if (pending) flushAgentPreviewNow(pending);
      }, delay);
    },
    [flushAgentPreviewNow],
  );

  const clearAgentPreviewDebounce = useCallback(() => {
    const state = previewRefreshRef.current;
    if (state.timer) {
      window.clearTimeout(state.timer);
      state.timer = 0;
    }
    state.pending = null;
  }, []);

  const resetAgentSessionUi = useCallback(() => {
    setAgentWorkPlan([]);
    setAgentTodos([]);
    setAgentToolSteps([]);
    agentToolStepsRef.current = [];
    setAgentPartialProgress(null);
    setClarifications([]);
    setPreviewAutomationState("idle");
    const state = previewRefreshRef.current;
    if (state.timer) {
      window.clearTimeout(state.timer);
      state.timer = 0;
    }
    state.pending = null;
    state.lastAt = 0;
  }, []);

  const stopActiveAgentRequest = useCallback(() => {
    void cancelDesignerAgentSession().catch(() => {});
    chatRunIdRef.current += 1;
    chatAbortRef.current?.abort();
    chatAbortRef.current = null;
    resetAgentSessionUi();
    setBusy(false);
    setError(null);
  }, [resetAgentSessionUi]);

  const liveProgressHandlers = useCallback(
    () => ({
      setAgentWorkPlan,
      setAgentTodos,
      setAgentToolSteps,
      agentTodosRef,
      agentToolStepsRef,
      applyPreview: applyAgentPreviewSnapshot,
    }),
    [applyAgentPreviewSnapshot],
  );

  useEffect(() => {
    if (busy) return;
    const restored = restoreDesignerActionUi(history);
    setAgentPartialProgress(restored.partialProgress);
    setClarifications(restored.clarifications);
    let todos = restored.agentTodos;
    if (isPlanningOnlyTodos(todos)) {
      todos = [];
    }
    setAgentTodos(todos);
    agentTodosRef.current = todos;
    if (todos.length === 0) {
      setAgentWorkPlan([]);
    }
  }, [history, busy]);

  useEffect(() => {
    if (!authed || busy) return;
    let cancelled = false;
    void (async () => {
      try {
        const snap = await fetchDesignerLiveProgress();
        if (cancelled) return;
        if (!snap.active) return;
        if (!liveProgressSnapshotHasWork(snap)) {
          await cancelDesignerAgentSession();
          return;
        }
        if (shouldResumeBusyFromLiveProgress(snap)) {
          const handlers = liveProgressHandlers();
          applyDesignerLiveProgressSnapshot(snap, handlers);
          setBusy(true);
          return;
        }
        await cancelDesignerAgentSession();
      } catch {
        /* optional */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authed, activeId, busy, liveProgressHandlers]);

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
          setSavedSnapshot(
            buildPersistSnapshot(
              match.name,
              match.html_markup,
              match.css_stylesheet,
              match.js_script || "",
              match.chat_history_json || [],
            ),
          );
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

  useEffect(() => {
    if (!busy) return;
    let cancelled = false;
    const applyPoll = async () => {
      try {
        const snap = await fetchDesignerLiveProgress();
        if (cancelled || !snap.active) return;
        applyDesignerLiveProgressSnapshot(snap, liveProgressHandlers());
      } catch {
        /* poll optional */
      }
    };
    void applyPoll();
    const pollId = window.setInterval(() => void applyPoll(), 750);
    return () => {
      cancelled = true;
      window.clearInterval(pollId);
    };
  }, [busy, liveProgressHandlers]);

  useLayoutEffect(() => {
    syncComposerTextareaHeight();
  }, [draft, syncComposerTextareaHeight]);

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape" && previewPickMode) {
        setPreviewPickMode(false);
        return;
      }
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
  }, [previewPickMode]);

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
    setTemplateMenuOpenId(null);
    setTemplateHistoryOpen(false);
    setSavedSnapshot(
      buildPersistSnapshot(t.name, t.html_markup, t.css_stylesheet, t.js_script || "", t.chat_history_json || []),
    );
    dismissSnackbar();
  };

  const clearConversation = async () => {
    stopActiveAgentRequest();
    setHistory([]);
    setPinnedIdx(new Set());
    setConfirmClear(false);
    if (!activeId) {
      showSnackbar("Conversation cleared.", "success");
      return;
    }
    try {
      await updateTemplate(activeId, { chat_history_json: [] });
      setTemplates((list) =>
        list.map((t) => (t.id === activeId ? { ...t, chat_history_json: [] } : t)),
      );
      setSavedSnapshot((prev) =>
        prev
          ? { ...prev, historyKey: "[]" }
          : buildPersistSnapshot(name, html, css, js || "", []),
      );
      showSnackbar("Conversation cleared and agent stopped.", "success");
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
    setSavedSnapshot(buildPersistSnapshot("Untitled theme", "", "", "", []));
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
      setPreviewDoc(applyLivePreviewDocumentChrome(data.compiled_html || ""));
    } else {
      setPreviewDoc(compileLocalTemplatePreview(html, css, js));
    }
  }, [css, html, js, showSampleData]);

  useEffect(() => {
    if (!authed) return;
    refreshPreview().catch(() => setPreviewDoc(""));
  }, [authed, refreshPreview]);

  const uploadFiles = useCallback(async (files: FileList | File[]) => {
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
  }, [activeId]);

  const onComposerPaste = useCallback(
    (e: ClipboardEvent<HTMLTextAreaElement>) => {
      const raw = imageFilesFromClipboardEvent(e.nativeEvent);
      if (raw.length === 0 || busy || uploading) return;
      e.preventDefault();
      const files = raw.map((f, i) => labelPastedScreenshotFile(f, i));
      showSnackbar(
        files.length === 1 ? "Screenshot pasted — uploading…" : `${files.length} images pasted — uploading…`,
        "success",
      );
      void uploadFiles(files);
    },
    [busy, uploading, showSnackbar, uploadFiles],
  );

const FLOORPLAN_UPLOAD_CHIP = /upload.*floorplan|floorplan.*upload|attach.*floorplan|i'?ll upload a floorplan/i;
const PREVIEW_ISSUE_MESSAGE = /preview|not showing|close button|looks wrong|debug|overlap|map always|why now/i;

  const sendMessage = async (textOverride?: string) => {
    const text = (textOverride ?? draft).trim();
    if ((!text && attachments.length === 0 && !previewElementTarget) || busy) return;

    if (text && FLOORPLAN_UPLOAD_CHIP.test(text) && attachments.length === 0) {
      showSnackbar("Attach a floorplan image first (paperclip or drag-and-drop), then send.", "warning");
      fileInputRef.current?.click();
      return;
    }

    lastUserMessage.current = text;
    pushUndo();
    setBusy(true);
    setError(null);
    setClarifications([]);
    setPreviewAutomationState("idle");
    setPreviewPickMode(false);
    setAgentWorkPlan([]);
    setAgentTodos(PLANNING_WAIT_TODOS);
    agentTodosRef.current = PLANNING_WAIT_TODOS;
    setAgentToolSteps([]);
    agentToolStepsRef.current = [];
    setAgentPartialProgress(null);
    const runId = ++chatRunIdRef.current;
    const abortController = new AbortController();
    chatAbortRef.current = abortController;
    const isActiveRun = () => runId === chatRunIdRef.current;
    const pendingAttachments = [...attachments];
    const pendingPreviewTarget = previewElementTarget;
    const agentMessage =
      composeMessageWithPreviewTarget(text, pendingPreviewTarget) ||
      text ||
      "(attachments only)";
    const pendingUser: ChatMessage = {
      role: "user",
      content: text,
      ts: new Date().toISOString(),
      ...(pendingPreviewTarget
        ? { preview_target: previewTargetToAttachment(pendingPreviewTarget) }
        : {}),
    };
    setHistory((h) => [...h, pendingUser]);
    setDraft("");
    setAttachments([]);
    setPreviewElementTarget(null);
    try {
      const includeAudit =
        PREVIEW_ISSUE_MESSAGE.test(text) ||
        shouldAttachPreviewAutomation(text, false) ||
        Boolean(pendingPreviewTarget);
      let automationReport: PreviewAutomationReport | null = null;
      if (includeAudit && (html || css || js)) {
        if (showSampleData) {
          await refreshPreview();
          await new Promise((r) => window.setTimeout(r, 120));
        }
        setPreviewAutomationState("running");
        await waitForPreviewIframe(previewIframeRef.current, 5000);
        automationReport = await runPreviewPanelAutomation(
          previewIframeRef.current,
          previewDoc || undefined,
        );
        if (automationReport.error) {
          setPreviewAutomationState("error");
        } else {
          setPreviewAutomationState("used");
        }
      }

      const data = await streamDesignerChat(
        {
        message: agentMessage,
        display_message: text,
        preview_target: pendingPreviewTarget
          ? previewTargetToAttachment(pendingPreviewTarget)
          : null,
        history: history,
        html_markup: html,
        css_stylesheet: css,
        js_script: js,
        attachment_ids: pendingAttachments.map((a) => a.id),
        template_id: activeId || undefined,
        include_preview_audit: includeAudit,
        preview_automation_report: automationReport,
        preview_automation_depth: 0,
        },
        {
          onPlan: (steps) => {
            if (!isActiveRun()) return;
            flushSync(() => {
              setAgentWorkPlan(steps);
              if (isPlanningOnlyTodos(agentTodosRef.current)) {
                agentTodosRef.current = [];
                setAgentTodos([]);
              }
            });
          },
          onStep: (steps) => {
            if (!isActiveRun()) return;
            flushSync(() => {
              setAgentWorkPlan(steps);
              if (isPlanningOnlyTodos(agentTodosRef.current)) {
                agentTodosRef.current = [];
                setAgentTodos([]);
              }
            });
          },
          onTodo: (todos) => {
            if (!isActiveRun()) return;
            const normalized = normalizeAgentWorkPlanSteps(todos);
            if (normalized.length === 0) return;
            if (isPlanningOnlyTodos(normalized)) return;
            flushSync(() => {
              agentTodosRef.current = normalized;
              setAgentTodos(normalized);
            });
          },
          onDone: (response) => {
            if (!isActiveRun()) return;
            const normalized = normalizeAgentWorkPlanSteps(response.agent_todos);
            if (normalized.length === 0) return;
            flushSync(() => {
              agentTodosRef.current = normalized;
              setAgentTodos(normalized);
            });
          },
          onError: (message) => {
            if (!isActiveRun()) return;
            setError(message);
            showSnackbar(message, "error");
          },
          onStatus: (payload) => {
            if (!isActiveRun()) return;
            if (payload.kind === "model_api_error" && payload.message) {
              showSnackbar(payload.message, "warning");
            }
          },
          onPreview: (snap) => {
            if (!isActiveRun()) return;
            applyAgentPreviewSnapshot(snap);
          },
          onTool: (step) => {
            if (!isActiveRun()) return;
            flushSync(() => {
              setAgentToolSteps((prev) => {
                const next = [...prev, step].slice(-24);
                agentToolStepsRef.current = next;
                return next;
              });
            });
          },
        },
        abortController.signal,
      );
      if (!isActiveRun()) return;
      setHistory(data.history || []);
      setHtml(data.html_markup || html);
      setCss(data.css_stylesheet || css);
      setJs(data.js_script || js);
      flushAgentPreviewNow({
        html_markup: data.html_markup || html,
        css_stylesheet: data.css_stylesheet || css,
        js_script: data.js_script || js,
      });
      clearAgentPreviewDebounce();
      if (data.work_plan?.length) {
        setAgentWorkPlan(data.work_plan);
      }
      if (data.agent_todos?.length) {
        let normalized = normalizeAgentWorkPlanSteps(data.agent_todos);
        if (!data.partial_completion && !data.model_api_error) {
          normalized = collapseCompletedExecutionTodos(normalized);
        }
        agentTodosRef.current = normalized;
        setAgentTodos(normalized);
      } else if (isPlanningOnlyTodos(agentTodosRef.current)) {
        agentTodosRef.current = [];
        setAgentTodos([]);
      } else if (!data.partial_completion && !data.model_api_error) {
        agentTodosRef.current = [];
        setAgentTodos([]);
        setAgentWorkPlan([]);
      }
      setClarifications(data.clarification_options || []);
      if (data.partial_completion && data.continuation_recommended) {
        const completed =
          data.progress_completed?.length
            ? data.progress_completed
            : agentToolStepsRef.current.map((t, idx) => ({
                id: `live-${idx}`,
                label: `${t.phase === "repair" ? "Fix: " : ""}${t.label}`,
                ok: t.ok,
              }));
        setAgentPartialProgress({
          completed,
          remaining: data.remaining_items ?? [],
        });
        showSnackbar("Partial update — use Continue in the progress card or pick an option below.", "warning");
      } else if (data.model_api_error) {
        showSnackbar(
          "Design model timed out during validation repair. Preview kept from the last successful edit.",
          "warning",
        );
      } else {
        setAgentPartialProgress(null);
        if (!data.agent_todos?.length) {
          setAgentToolSteps([]);
        }
      }
      dismissSnackbar();
      if (data.attachment_required) {
        showSnackbar("Attach a floorplan image, then send again.", "warning");
      } else if (data.preview_automation_used) {
        setPreviewAutomationState("used");
      } else if (automationReport && !automationReport.error) {
        setPreviewAutomationState("idle");
      }
      if (data.preview_audit_findings?.length) {
        showSnackbar(
          `Preview check: ${data.preview_audit_findings.length} issue(s) — agent applied fixes where possible.`,
          "warning",
        );
      }
      if (data.self_check?.valid) {
        setSrStatus("Agent updated the proposal (automatic checks passed).");
      } else {
        setSrStatus("Agent updated the proposal template.");
      }
      const nextHistory = data.history || [];
      const nextHtml = data.html_markup || html;
      const nextCss = data.css_stylesheet || css;
      const nextJs = data.js_script || js;
      const agentChanged =
        nextHtml !== html ||
        nextCss !== css ||
        nextJs !== js ||
        JSON.stringify(nextHistory) !== JSON.stringify(history);
      if (agentChanged || !activeId) {
        try {
          await saveActiveTemplate({
            silent: true,
            override: {
              html: nextHtml,
              css: nextCss,
              js: nextJs,
              history: nextHistory,
            },
          });
        } catch {
          showSnackbar("Agent finished but auto-save failed — use Save on the template card.", "warning");
        }
      }
    } catch (e) {
      if (!isActiveRun() || (e instanceof DOMException && e.name === "AbortError")) {
        return;
      }
      setError("Design agent request failed.");
      setHistory((h) => h.filter((m) => m !== pendingUser));
      setAttachments(pendingAttachments);
      setPreviewAutomationState("error");
    } finally {
      if (isActiveRun()) {
        clearAgentPreviewDebounce();
        setBusy(false);
        chatAbortRef.current = null;
      }
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

  const handleExport = useCallback(async () => {
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
  }, [activeId, css, history, html, js, name]);

  const saveActiveTemplate = useCallback(
    async (opts?: {
      silent?: boolean;
      override?: { name?: string; html?: string; css?: string; js?: string; history?: ChatMessage[] };
    }) => {
      const payloadName = opts?.override?.name ?? name;
      const payloadHtml = opts?.override?.html ?? html;
      const payloadCss = opts?.override?.css ?? css;
      const payloadJs = opts?.override?.js ?? js;
      const payloadHistory = opts?.override?.history ?? history;
      if (!opts?.silent) setBusy(true);
      try {
        const payload = {
          name: payloadName,
          html_markup: payloadHtml,
          css_stylesheet: payloadCss,
          js_script: payloadJs,
          chat_history_json: payloadHistory,
          is_default: false,
        };
        let saved: ProposalTemplate;
        if (activeId) saved = await updateTemplate(activeId, payload);
        else {
          saved = await saveTemplate(payload);
          setActiveId(saved.id);
        }
        if (opts?.silent) {
          setName(saved.name);
          setHtml(saved.html_markup || payloadHtml);
          setCss(saved.css_stylesheet || payloadCss);
          setJs(saved.js_script || payloadJs);
          setHistory(saved.chat_history_json || payloadHistory);
          setRevisions(saved.revision_history_json || []);
          setSavedSnapshot(
            buildPersistSnapshot(
              saved.name,
              saved.html_markup || payloadHtml,
              saved.css_stylesheet || payloadCss,
              saved.js_script || payloadJs,
              saved.chat_history_json || payloadHistory,
            ),
          );
        } else {
          applyTemplate(saved);
        }
        await refreshTemplates();
        if (!opts?.silent) showSnackbar("Template saved successfully.", "success");
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Save failed";
        showSnackbar(msg, "error");
      } finally {
        if (!opts?.silent) setBusy(false);
      }
    },
    [activeId, css, history, html, js, name, refreshTemplates, showSnackbar, applyTemplate],
  );

  const templateCardActions = useMemo(
    () => ({
      onDuplicate: () => {
        if (!activeId) return;
        void (async () => {
          const c = await duplicateTemplate(activeId);
          await refreshTemplates();
          applyTemplate(c);
          setTemplateMenuOpenId(c.id);
        })();
      },
      onDelete: () => setConfirmDelete(true),
      onSetDefault: () => {
        if (!activeId) return;
        void updateTemplate(activeId, { is_default: true }).then(refreshTemplates);
      },
      onExport: () => void handleExport(),
    }),
    [activeId, refreshTemplates, handleExport],
  );

  const DRAFT_CARD_ID = "__draft__";

  const draftTemplatePreview = useMemo(
    (): ProposalTemplate => ({
      id: DRAFT_CARD_ID,
      name,
      html_markup: html,
      css_stylesheet: css,
      js_script: js,
      is_default: false,
      chat_history_json: history,
      updated_at: new Date().toISOString(),
    }),
    [css, history, html, js, name],
  );

  const showDraftCard = !activeId;

  const renderTemplateCard = (t: ProposalTemplate, opts?: { isDraft?: boolean }) => {
    const isDraft = opts?.isDraft ?? false;
    const cardId = isDraft ? DRAFT_CARD_ID : t.id;
    const selected = isDraft ? !activeId : activeId === t.id;
    return (
      <TemplateLibraryCard
        template={t}
        selected={selected}
        isDraft={isDraft}
        busy={busy}
        displayName={selected ? name : t.name}
        onNameChange={selected ? setName : undefined}
        menuOpen={templateMenuOpenId === cardId}
        onMenuToggle={() =>
          setTemplateMenuOpenId((open) => (open === cardId ? null : cardId))
        }
        actionsEnabled={selected}
        actions={templateCardActions}
        isDefault={!isDraft && Boolean(t.is_default)}
        revisions={selected && !isDraft ? revisions : t.revision_history_json || []}
        onOpenHistory={() => setTemplateHistoryOpen(true)}
        isDirty={selected && templateIsDirty}
        onSave={() => void saveActiveTemplate()}
        onSelect={() => {
          if (isDraft) return;
          applyTemplate(t);
        }}
      />
    );
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
        label={
          previewPickMode ? "Cancel point-to-select (Esc)" : "Point to a section in preview"
        }
        selected={previewPickMode}
        disabled={!previewDoc || busy}
        onClick={() => {
          setPreviewPickMode((on) => {
            const next = !on;
            if (next) {
              showSnackbar(
                "Click any section or element in the live preview to attach it.",
                "success",
              );
            }
            return next;
          });
        }}
      >
        <IconTargetPick />
      </TemplateIconButton>
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
            : "studio-shell-panel studio-live-preview-panel studio-live-preview-panel--inline"
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
            <div className="min-w-0 max-w-full shrink-0">{renderPreviewToolbar()}</div>
          </div>
        </header>
        <div
          className={`studio-live-preview-stage ${fullscreen ? "p-2 sm:p-3" : "p-4"}`}
        >
          <div className="mx-auto flex h-full w-full min-h-0 min-w-0 justify-center">
            <div
              className={`studio-live-preview-frame relative ${
                fullscreen && previewWidth === "full" ? "" : "studio-live-preview-frame--rounded"
              }`}
              style={{
                width: fullscreen && previewWidth === "full" ? "100%" : previewFrameWidth,
                maxWidth: "100%",
              }}
            >
              {previewDoc ? (
                <div
                  ref={previewScrollRef}
                  className={`studio-live-preview-scroll${previewPickMode ? " studio-live-preview-scroll--pick" : ""}`}
                >
                  <iframe
                    ref={previewIframeRef}
                    title="Proposal preview"
                    className="studio-live-preview-iframe"
                    sandbox="allow-scripts allow-same-origin"
                    srcDoc={previewDoc}
                    style={{ height: livePreviewIframeHeight ?? "100%" }}
                  />
                  <PreviewTargetHighlight
                    hoverBox={previewHoverBox}
                    lockedBox={previewLockedBox}
                    pickMode={previewPickMode}
                    contentHeight={livePreviewIframeHeight ?? 480}
                    shieldRef={previewPickShieldRef}
                  />
                </div>
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
      <AgentRulesDialog open={showAgentRules} onClose={() => setShowAgentRules(false)} />
      <TemplateVersionHistoryDialog
        open={templateHistoryOpen && Boolean(activeId)}
        templateName={name}
        revisions={revisions}
        busy={busy}
        onClose={() => setTemplateHistoryOpen(false)}
        onRestore={(index) => {
          if (!activeId) return;
          void (async () => {
            setBusy(true);
            try {
              const t = await restoreRevision(activeId, index);
              applyTemplate(t);
              await refreshTemplates();
              showSnackbar("Restored template version.", "success");
              setTemplateHistoryOpen(false);
            } catch {
              showSnackbar("Could not restore version.", "error");
            } finally {
              setBusy(false);
            }
          })();
        }}
      />
      <ConfirmDialog open={confirmClear} title="Clear conversation?" message="Stops any in-progress design agent work and permanently clears chat for this template." onCancel={() => setConfirmClear(false)} onConfirm={() => void clearConversation()} />
      <ConfirmDialog open={confirmDelete} title="Delete template?" message="This permanently removes the template from your library." confirmLabel="Delete" onCancel={() => setConfirmDelete(false)} onConfirm={async () => { if (activeId) { await deleteTemplate(activeId); setActiveId(null); newTemplate(); await refreshTemplates(); } setConfirmDelete(false); }} />

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden px-4 pb-[var(--studio-safe-bottom)] pt-3 sm:flex-row sm:px-6">
        <aside className="studio-shell-panel flex max-h-[32vh] w-full shrink-0 flex-col sm:max-h-none sm:w-64">
          <div className="studio-panel-header !min-h-[4rem]">
            <div>
              <p className="studio-panel-kicker">Library</p>
              <h2 className="font-semibold">Templates</h2>
            </div>
            <button type="button" onClick={newTemplate} className="studio-btn-secondary !min-h-0 px-2.5 py-1.5 text-[11px]">+ New</button>
          </div>
          <div className="studio-panel-body !pb-2">
            <label className="studio-field-label mb-1.5 block text-[10px] font-medium uppercase tracking-wide">Search templates</label>
            <div className="relative">
              <span className="studio-field-search-icon" aria-hidden>
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
          <ul className="studio-scroll min-h-0 flex-1 space-y-2.5 overflow-y-auto px-[var(--studio-inset-x)] pb-3">
            {showDraftCard && (
              <li>{renderTemplateCard(draftTemplatePreview, { isDraft: true })}</li>
            )}
            {filteredTemplates.map((t) => (
              <li key={t.id}>{renderTemplateCard(t)}</li>
            ))}
            {!showDraftCard && filteredTemplates.length === 0 && (
              <li className="studio-empty-list">
                No templates match your search.
              </li>
            )}
          </ul>
        </aside>

        <section
          className="studio-shell-panel relative flex min-h-0 min-w-0 flex-1 flex-col bg-white/[0.03]"
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={async (e: DragEvent) => { e.preventDefault(); setDragActive(false); if (e.dataTransfer.files?.length) await uploadFiles(e.dataTransfer.files); }}
        >
          <AnimatePresence>
            {dragActive && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="pointer-events-none absolute inset-3 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-violet-300 bg-violet-600/25">
                <p className="text-lg font-semibold">Release to upload</p>
              </motion.div>
            )}
          </AnimatePresence>
          <header className="studio-panel-header">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold">Design Agent</h2>
                <PreviewAutomationIndicator state={previewAutomationState} />
              </div>
              <p className="studio-panel-subtitle">
                Proposal + interactive venue map · attach floorplan when asked · say “skip questions” to auto-build
              </p>
            </div>
            <div className="studio-toolbar">
              <TemplateIconButton micro label="Agent rules" onClick={() => setShowAgentRules(true)}>
                <IconAgentRules />
              </TemplateIconButton>
              <TemplateIconButton micro label="Keyboard shortcuts" onClick={() => setShowHelp(true)}>
                <IconHelp />
              </TemplateIconButton>
              <TemplateIconButton micro label="Media library" onClick={() => setShowLibrary(true)}>
                <IconMediaLibrary />
              </TemplateIconButton>
              <TemplateIconButton
                micro
                label="Regenerate last response"
                disabled={!lastUserMessage.current || busy}
                onClick={regenerate}
              >
                <IconRegenerate />
              </TemplateIconButton>
              <TemplateIconButton micro label="Undo layout" disabled={undoStack.length === 0} onClick={undo}>
                <IconUndo />
              </TemplateIconButton>
              <TemplateIconButton micro label="Clear chat" variant="danger" onClick={() => setConfirmClear(true)}>
                <IconClearChat />
              </TemplateIconButton>
            </div>
          </header>
          <div className="studio-scroll min-h-0 flex-1 space-y-3 overflow-x-hidden overflow-y-auto px-[var(--studio-inset-x)] py-4">
            {history.length === 0 && (
              <div className="studio-chat-empty">
                <p className="studio-chat-empty-title font-medium">Start designing</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUGGESTED_PROMPTS.map((p) => (
                    <button key={p} type="button" className="studio-suggest-chip" onClick={() => void sendMessage(p)} disabled={busy}>{p}</button>
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
                  <button key={c} type="button" className="rounded-full bg-fuchsia-600/30 px-3 py-1 text-xs hover:bg-fuchsia-600/50" onClick={() => {
                    if (FLOORPLAN_UPLOAD_CHIP.test(c) && attachments.length === 0) {
                      showSnackbar("Attach a floorplan image first, then tap this again or send.", "warning");
                      fileInputRef.current?.click();
                      return;
                    }
                    void sendMessage(c);
                  }}>{c}</button>
                ))}
              </div>
            )}
            <DesignerAgentProgress
              active={agentProgressUi.progressActive}
              showProgressIframe={agentProgressUi.showProgressIframe}
              steps={agentWorkPlan}
              tasks={agentTodos}
              previewDoc={agentWorkingPreviewDoc}
              continuation={
                !busy && agentPartialProgress
                  ? {
                      completed: agentPartialProgress.completed,
                      remaining: agentPartialProgress.remaining,
                      onContinue: () => {
                        setAgentPartialProgress(null);
                        void sendMessage("Continue — finish the remaining edits");
                      },
                      onDismiss: () => {
                        setAgentPartialProgress(null);
                        setClarifications([]);
                        const nextHistory = dismissLatestAssistantActionState(history);
                        setHistory(nextHistory);
                        void saveActiveTemplate({ silent: true, override: { history: nextHistory } });
                      },
                    }
                  : null
              }
            />
            <div ref={chatEndRef} />
          </div>
          {uploadRows.length > 0 && (
            <div className="space-y-1 px-[var(--studio-inset-x)] pb-2">
              {uploadRows.map((u) => (
                <div key={u.id} className="studio-composer-upload-row">
                  {u.name} — {u.status === "uploading" ? `${u.progress}%` : u.status}
                  {u.status === "uploading" && <div className="mt-0.5 h-1 rounded bg-white/10"><div className="h-1 rounded bg-violet-500 transition-all" style={{ width: `${u.progress}%` }} /></div>}
                </div>
              ))}
            </div>
          )}
          {!dragActive && attachments.length === 0 && (
            <div className="studio-composer-dropzone">
              <span aria-hidden>⬆</span>
              Drag & drop images or videos here
            </div>
          )}
          {previewElementTarget && (
            <div className="flex flex-wrap gap-2 px-[var(--studio-inset-x)] pb-2">
              <div className="studio-preview-target-chip">
                <IconTargetPick />
                <span className="min-w-0 truncate">
                  {previewElementTarget.sectionLabel ||
                    previewElementTarget.textSnippet.slice(0, 48) ||
                    "Selected section"}
                </span>
                <button
                  type="button"
                  className="ml-1 rounded px-1 text-white/70 hover:bg-white/10"
                  aria-label="Clear preview target"
                  onClick={() => setPreviewElementTarget(null)}
                >
                  ×
                </button>
              </div>
            </div>
          )}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 px-[var(--studio-inset-x)] pb-2">
              {attachments.map((a) => (
                <div key={a.id} className="studio-attachment-chip">
                  {a.media_type === "VIDEO" ? <video src={a.url} className="h-11 w-16 rounded-md object-cover" muted /> : <img src={a.url} alt="" className="h-11 w-16 rounded-md object-cover" />}
                  <span className="max-w-[90px] truncate">{a.original_name}</span>
                  <button type="button" onClick={() => setAttachments((p) => p.filter((x) => x.id !== a.id))}>×</button>
                </div>
              ))}
            </div>
          )}
          {mentionOpen && mentionSuggestions.length > 0 && (
            <ul className="studio-mention-popover studio-scroll mx-[var(--studio-inset-x)] mb-2 max-h-32">
              {mentionSuggestions.slice(0, 8).map((a) => (
                <li key={a.id}><button type="button" className="studio-mention-option" onClick={() => insertMention(a)}>{a.original_name}</button></li>
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
                  onPaste={onComposerPaste}
                  placeholder="Message the design agent… use preview target icon · @ mention · paste screenshot"
                  disabled={busy}
                  aria-label="Message to design agent"
                />
                <motion.button
                  type="submit"
                  disabled={busy || uploading || (!draft.trim() && attachments.length === 0 && !previewElementTarget)}
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
            </div>
            <p className="studio-composer-hint">
              Enter to send · Shift+Enter for new line · preview target button scopes edits to one section
            </p>
          </form>
      </section>

        {!previewFullscreen && previewPanel}
        {fullscreenPreviewPortal}
      </div>
    </div>
  );
}
