import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import ParticleConstellation from "../components/canvas3d/ParticleConstellation";
import CentralVoiceOrb from "../components/canvas3d/CentralVoiceOrb";
import ComposerDock from "../components/composer/ComposerDock";
import WindowDragAndDropOverlay from "../components/composer/WindowDragAndDropOverlay";
import AgentAvailabilityTable from "../components/generative_ui/AgentAvailabilityTable";
import AgentCardDeck from "../components/generative_ui/AgentCardDeck";
import ProposalTemplateRenderer from "../components/generative_ui/ProposalTemplateRenderer";
import VoiceAgentSubtitles, { type CaptionLine } from "../components/voice/VoiceAgentSubtitles";
import ClientSessionHistoryRail from "../components/client/ClientSessionHistoryRail";
import { primeSessionProposalPreviewCache } from "../components/client/ClientSessionProposalPreview";
import { useVoiceOrbAudio } from "../hooks/useVoiceOrbAudio";
import { useBrowserVoiceTranscribe } from "../hooks/useBrowserVoiceTranscribe";
import { useBidirectionalAgentUI } from "../hooks/useBidirectionalAgentUI";
import { unlockBrowserAudio, primeAudioSync, useSeamlessM4TV2 } from "../hooks/useSeamlessM4TV2";
import type { AgentUiComponent } from "../lib/agentUiComponents";
import { useClientCardDeckVisibility } from "../hooks/useClientCardDeckVisibility";
import { cardsHaveIdentifiedFields, messageIsSocialGreeting, quickVoiceAck, shouldEnsureRfpSession, shouldRunDebateExtraction } from "../lib/rfpFlow";
import { createRfpSession, fetchRfpCards, renderClientProposal, userMessageConfirmsBooking, waitForRfpCards } from "../lib/rfpApi";
import { streamAssistantReply } from "../lib/voiceChatStream";
import { sanitizeClientMessage } from "../lib/sanitizeClientMessage";
import type { ProposalInteractionPayload } from "../lib/proposalClientBridge";
import {
  fetchClientRfpSession,
  listClientRfpSessions,
  setClientRfpSessionArchived,
  type ClientRfpSessionSummary,
} from "../lib/clientApi";
import { useClientPortalAuth } from "../hooks/useClientPortalAuth";
import { useAppShell } from "../context/AppShellContext";

function newCaptionId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function ClientWorkspace() {
  const { clientSubtitlesEnabled, setClientProposalFullscreen } = useAppShell();
  const { authed, bootstrapping } = useClientPortalAuth();
  const [sessionSummaries, setSessionSummaries] = useState<ClientRfpSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [archiveBusyId, setArchiveBusyId] = useState<string | null>(null);
  const [sessionCompleted, setSessionCompleted] = useState(false);
  const [composerOpen, setComposerOpen] = useState(true);
  const [proposalPresentation, setProposalPresentation] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  sessionIdRef.current = sessionId;
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [voiceBlocked, setVoiceBlocked] = useState(false);
  const [statusHint, setStatusHint] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [progressText, setProgressText] = useState<string | null>(null);
  const [captions, setCaptions] = useState<CaptionLine[]>([]);
  const [agentUiComponent, setAgentUiComponent] = useState<AgentUiComponent | null>(null);
  const [selectedAvailabilityIso, setSelectedAvailabilityIso] = useState<string | null>(null);
  const lastSpokenRef = useRef<{ text: string; at: number } | null>(null);
  const pendingSpeechRef = useRef<{ text: string; captionId: string } | null>(null);
  const activeCaptionRef = useRef<string | null>(null);
  const askAssistantRef = useRef<(msg: string, opts?: { skipUserCaption?: boolean }) => Promise<void>>(
    async () => {},
  );
  const liveUserCaptionRef = useRef<string | null>(null);
  const lastVoiceTurnRef = useRef<{ text: string; at: number } | null>(null);
  const [micLevels, setMicLevels] = useState<number[]>(() => Array(24).fill(0.12));
  const [voiceMode, setVoiceMode] = useState(false);
  const voiceModeRef = useRef(false);
  voiceModeRef.current = voiceMode;
  const { synthesizePulse } = useVoiceOrbAudio(false);

  const appendCaption = useCallback((role: CaptionLine["role"], text: string, status: CaptionLine["status"] = "done") => {
    const line: CaptionLine = {
      id: newCaptionId(),
      role,
      text,
      reveal: role === "user" ? 1 : 0,
      status,
    };
    setCaptions((prev) => [...prev.slice(-8), line]);
    return line.id;
  }, []);

  const patchCaption = useCallback((id: string, patch: Partial<CaptionLine>) => {
    setCaptions((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  }, []);

  const finishCaptionReveal = useCallback(
    (captionId: string, durationMs = 800) => {
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / durationMs);
        patchCaption(captionId, { reveal: t, status: t >= 1 ? "done" : "speaking" });
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    },
    [patchCaption],
  );

  const { speak, stopSpeaking } = useSeamlessM4TV2(
    () => {
      setAgentSpeaking(true);
      setThinking(false);
    },
    () => {
      setAgentSpeaking(false);
      if (activeCaptionRef.current) {
        const id = activeCaptionRef.current;
        patchCaption(id, { reveal: 1, status: "done" });
        activeCaptionRef.current = null;
      }
    },
  );

  const stopListeningRef = useRef<() => void>(() => {});
  const pauseListeningRef = useRef<() => void>(() => {});
  const resumeListeningRef = useRef<() => void>(() => {});

  const speakOnce = useCallback(
    async (text: string, captionId?: string, opts?: { mandatory?: boolean }) => {
      const normalized = text.trim();
      if (!normalized) return;

      pauseListeningRef.current();

      const last = lastSpokenRef.current;
      if (
        !opts?.mandatory &&
        last &&
        last.text === normalized &&
        Date.now() - last.at < 6000
      ) {
        if (captionId) {
          patchCaption(captionId, { reveal: 1, status: "done" });
        }
        if (voiceModeRef.current) {
          void resumeListeningRef.current();
        }
        return;
      }

      if (opts?.mandatory) {
        lastSpokenRef.current = null;
      }

      if (captionId) {
        patchCaption(captionId, { status: "speaking", reveal: 0 });
        activeCaptionRef.current = captionId;
      }

      const result = await speak(normalized, {
        onProgress: (current, duration) => {
          if (!captionId || duration <= 0) return;
          patchCaption(captionId, {
            reveal: Math.min(1, current / duration),
            status: "speaking",
          });
        },
      });

      if (result.ok) {
        lastSpokenRef.current = { text: normalized, at: Date.now() };
        setVoiceBlocked(false);
        setStatusHint(null);
        if (voiceModeRef.current) {
          primeAudioSync();
          void resumeListeningRef.current();
        }
        return;
      }

      if (captionId) {
        finishCaptionReveal(captionId);
      }

      if (result.reason === "play_blocked") {
        pendingSpeechRef.current = { text: normalized, captionId: captionId || "" };
        setVoiceBlocked(true);
        setStatusHint("Live voice is required — tap Enable voice, then Send again.");
        if (voiceModeRef.current) {
          void resumeListeningRef.current();
        }
        return;
      }
      if (result.reason === "aborted") {
        setStatusHint("Voice playback was interrupted. Send again.");
        if (voiceModeRef.current) {
          void resumeListeningRef.current();
        }
        return;
      }
      setStatusHint(
        `Voice playback failed (${result.reason}${result.detail ? `: ${result.detail}` : ""}). Check backend on :8000.`,
      );
      if (voiceModeRef.current) {
        void resumeListeningRef.current();
      }
    },
    [speak, patchCaption, finishCaptionReveal],
  );

  const handleAgentUtterance = useCallback(
    (text: string, options?: { mandatory?: boolean }) => {
      if (!options?.mandatory) return;
      const captionId = appendCaption("agent", text, "pending");
      void speakOnce(text, captionId, { mandatory: true });
    },
    [appendCaption, speakOnce],
  );

  const { cards, proposalHtml, debateRings, error, submitCardMutation, submitProposalInteraction, markCardSaving, clientSession, cardSaveState, cardValidationError, setCards, clearProposalHtml, setProposalHtml, hydrateSession } =
    useBidirectionalAgentUI(sessionId, handleAgentUtterance);

  useEffect(() => {
    if (proposalHtml) {
      setProposalPresentation(true);
      setComposerOpen(true);
    }
  }, [proposalHtml]);

  useEffect(() => {
    setClientProposalFullscreen(proposalPresentation);
    return () => setClientProposalFullscreen(false);
  }, [proposalPresentation, setClientProposalFullscreen]);

  const refreshSessions = useCallback(async () => {
    if (!authed) return;
    setSessionsLoading(true);
    try {
      setSessionSummaries(await listClientRfpSessions());
    } finally {
      setSessionsLoading(false);
    }
  }, [authed]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const activateSession = useCallback(
    async (id: string) => {
      const detail = await fetchClientRfpSession(id);
      if (!detail) return;
      setSessionId(id);
      sessionIdRef.current = id;
      setSessionCompleted(detail.completed);
      setCards(detail.active_ui_cards_json || {});
      hydrateSession({ active_ui_cards_json: detail.active_ui_cards_json, client_session_json: detail.client_session });
      setCaptions([]);
      setAgentUiComponent(null);
      if (detail.completed) {
        const html = await renderClientProposal(id);
        if (html) {
          primeSessionProposalPreviewCache(id, html);
          setProposalHtml(html);
          setProposalPresentation(true);
        }
      } else {
        setProposalPresentation(false);
        clearProposalHtml();
      }
    },
    [clearProposalHtml, hydrateSession, setCards, setProposalHtml],
  );

  const openProposalView = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    const html = await renderClientProposal(sid);
    if (html) {
      primeSessionProposalPreviewCache(sid, html);
      setProposalHtml(html);
      setProposalPresentation(true);
    }
  }, [setProposalHtml]);

  const ensureSession = useCallback(
    async (
      userMessage: string,
      runDebate: boolean,
      onProgress?: (message: string) => void,
    ): Promise<{ id: string; created: boolean; voiceIntro?: string } | { error: string }> => {
      onProgress?.("Checking your RFP session…");
      if (sessionIdRef.current) {
        const hydrated = await waitForRfpCards(sessionIdRef.current);
        if (cardsHaveIdentifiedFields(hydrated)) {
          setCards(hydrated);
        }
        return { id: sessionIdRef.current, created: false };
      }
      onProgress?.("Creating your draft and running venue analysis…");
      const created = await createRfpSession(userMessage, runDebate);
      if (!created.ok) return { error: created.message };
      setSessionId(created.id);
      sessionIdRef.current = created.id;
      setSessionCompleted(false);
      void refreshSessions();
      if (runDebate) {
        if (cardsHaveIdentifiedFields(created.cards)) {
          setCards(created.cards);
        } else {
          onProgress?.("Pulling room block, meeting space, and pricing cards…");
          const hydrated = await waitForRfpCards(created.id);
          if (cardsHaveIdentifiedFields(hydrated)) {
            setCards(hydrated);
          }
        }
      }
      lastSpokenRef.current = null;
      return {
        id: created.id,
        created: true,
        voiceIntro: created.voiceIntro || undefined,
      };
    },
    [refreshSessions, setCards],
  );

  useEffect(() => {
    if (!sessionId || cardsHaveIdentifiedFields(cards)) return;
    let cancelled = false;
    void waitForRfpCards(sessionId).then((next) => {
      if (!cancelled && cardsHaveIdentifiedFields(next)) {
        setCards(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId, cards, setCards]);

  const askAssistant = useCallback(
    async (userMessage: string, opts?: { skipUserCaption?: boolean }) => {
      userMessage = sanitizeClientMessage(userMessage);
      if (!userMessage) return;
      if (!opts?.skipUserCaption) {
        appendCaption("user", userMessage);
      }
      setThinking(true);
      if (!messageIsSocialGreeting(userMessage)) {
        setProgressText(quickVoiceAck(userMessage));
      } else {
        setProgressText(null);
      }
      setAgentUiComponent(null);
      let agentCaptionId: string | null = null;
      let streamedText = "";

      const touchAgentLine = (text: string, status: CaptionLine["status"] = "speaking") => {
        setProgressText(text);
        if (!agentCaptionId) {
          agentCaptionId = appendCaption("agent", text, status);
        } else {
          patchCaption(agentCaptionId, { text, reveal: 1, status });
        }
      };

      try {
        const startPipeline = shouldRunDebateExtraction(userMessage) && !sessionIdRef.current;

        if (startPipeline) {
          touchAgentLine(quickVoiceAck(userMessage));
          const session = await ensureSession(userMessage, true, (msg) => touchAgentLine(msg));
          if ("error" in session) {
            setStatusHint(session.error);
            if (voiceModeRef.current) {
              void resumeListeningRef.current();
            }
            return;
          }
          if (session.created && session.voiceIntro) {
            touchAgentLine(session.voiceIntro, "pending");
            await speakOnce(session.voiceIntro, agentCaptionId!, { mandatory: true });
            return;
          }
        }

        if (!sessionIdRef.current && shouldEnsureRfpSession(userMessage)) {
          const created = await createRfpSession(userMessage.slice(0, 5000), false);
          if (created.ok) {
            setSessionId(created.id);
            sessionIdRef.current = created.id;
            setSessionCompleted(false);
            void refreshSessions();
            if (cardsHaveIdentifiedFields(created.cards)) setCards(created.cards);
          }
        }

        const turn = await streamAssistantReply(userMessage, sessionIdRef.current, {
          onStatus: (text) => touchAgentLine(text),
          onToken: (token) => {
            streamedText += token;
            touchAgentLine(streamedText.trim());
          },
          onDone: (finalReply, ui) => {
            streamedText = finalReply;
            touchAgentLine(finalReply, "pending");
            if (ui) setAgentUiComponent(ui);
          },
          onError: (message) => {
            touchAgentLine(message, "pending");
          },
        });

        const reply = turn.reply;
        if (turn.uiComponent) setAgentUiComponent(turn.uiComponent);

        const captionId = agentCaptionId ?? appendCaption("agent", reply, "pending");
        if (!agentCaptionId) agentCaptionId = captionId;
        patchCaption(captionId, { text: reply, reveal: 1, status: "pending" });
        await speakOnce(reply, captionId, { mandatory: true });

        const sid = sessionIdRef.current;
        if (sid) {
          const fresh = await fetchRfpCards(sid);
          if (cardsHaveIdentifiedFields(fresh)) setCards(fresh);
          if (userMessageConfirmsBooking(userMessage)) {
            const html = await renderClientProposal(sid);
            if (html) {
              primeSessionProposalPreviewCache(sid, html);
              setProposalHtml(html);
              setProposalPresentation(true);
              setSessionCompleted(true);
              void refreshSessions();
            }
          }
        }
      } finally {
        setThinking(false);
        setProgressText(null);
      }
    },
    [appendCaption, cards, ensureSession, patchCaption, refreshSessions, speakOnce],
  );

  askAssistantRef.current = askAssistant;

  const { startListening, pauseListening, resumeListening, stopListening, micPhase, isMicLive } =
    useBrowserVoiceTranscribe({
    onPartialTranscript: (text) => {
      if (!liveUserCaptionRef.current) {
        liveUserCaptionRef.current = appendCaption("user", text, "speaking");
      } else {
        patchCaption(liveUserCaptionRef.current, { text, reveal: 1, status: "speaking" });
      }
    },
    onFinalTranscript: (text) => {
      setStatusHint(null);
      const trimmed = text.trim();
      if (!trimmed) return;
      const last = lastVoiceTurnRef.current;
      if (last && last.text === trimmed && Date.now() - last.at < 1500) {
        return;
      }
      lastVoiceTurnRef.current = { text: trimmed, at: Date.now() };

      if (liveUserCaptionRef.current) {
        patchCaption(liveUserCaptionRef.current, { text: trimmed, status: "done", reveal: 1 });
        liveUserCaptionRef.current = null;
      } else {
        appendCaption("user", trimmed);
      }
      setThinking(true);
      primeAudioSync();
      pauseListeningRef.current();
      void unlockBrowserAudio().then(() =>
        askAssistantRef.current(trimmed, { skipUserCaption: true }),
      );
    },
    onError: (message) => {
      setStatusHint(message);
      const fatal =
        /denied|not supported|Could not start/i.test(message);
      if (fatal) setVoiceMode(false);
    },
    onLevels: (levels) => setMicLevels(levels),
  });
  stopListeningRef.current = stopListening;
  pauseListeningRef.current = pauseListening;
  resumeListeningRef.current = () => {
    if (!voiceModeRef.current) return;
    void resumeListening();
  };

  const toggleVoiceMode = useCallback(() => {
    if (agentSpeaking) return;
    if (voiceMode) {
      setVoiceMode(false);
      stopListening();
      liveUserCaptionRef.current = null;
      return;
    }
    setVoiceMode(true);
    primeAudioSync();
    void startListening();
  }, [agentSpeaking, voiceMode, startListening, stopListening]);

  const uploadFiles = useCallback(
    async (files: FileList) => {
      setDragging(false);
      await unlockBrowserAudio();
      const text = await files[0]?.text().catch(() => "MISMATCH_FIXTURE");
      appendCaption("user", text?.slice(0, 200) || "Uploaded RFP document");
      const created = await createRfpSession(text || "Corporate RFP", true);
      if (created.ok) {
        setSessionId(created.id);
        sessionIdRef.current = created.id;
        setSessionCompleted(false);
        void refreshSessions();
        const deck = cardsHaveIdentifiedFields(created.cards)
          ? created.cards
          : await waitForRfpCards(created.id);
        if (cardsHaveIdentifiedFields(deck)) {
          setCards(deck);
        }
        lastSpokenRef.current = null;
        synthesizePulse();
        if (created.voiceIntro) {
          const captionId = appendCaption("agent", created.voiceIntro, "pending");
          await speakOnce(created.voiceIntro, captionId, { mandatory: true });
        }
      } else {
        setStatusHint(created.message);
      }
    },
    [appendCaption, refreshSessions, setCards, speakOnce, synthesizePulse],
  );

  const onComposerSend = useCallback(
    (text: string) => {
      const cleaned = sanitizeClientMessage(text);
      if (!cleaned) return;
      primeAudioSync();
      void unlockBrowserAudio().then(async () => {
        synthesizePulse();
        await askAssistant(cleaned);
      });
    },
    [askAssistant, synthesizePulse],
  );

  const { showCardDeck, dockSideForGenerative } = useClientCardDeckVisibility(
    sessionId,
    cards,
    agentUiComponent,
  );
  const showSummaryDeck = showCardDeck && !proposalPresentation;

  const exitProposalView = useCallback(() => {
    setProposalPresentation(false);
    clearProposalHtml();
    setComposerOpen(true);
  }, [clearProposalHtml]);

  const startNewSession = useCallback(() => {
    setSessionId(null);
    sessionIdRef.current = null;
    setSessionCompleted(false);
    setProposalPresentation(false);
    clearProposalHtml();
    setCards({});
    hydrateSession({ active_ui_cards_json: {}, client_session_json: {} });
    setCaptions([]);
    setAgentUiComponent(null);
    setStatusHint(null);
    setComposerOpen(true);
    lastSpokenRef.current = null;
    liveUserCaptionRef.current = null;
  }, [clearProposalHtml, hydrateSession, setCards]);

  const handleArchiveSession = useCallback(
    async (id: string, archived: boolean) => {
      setArchiveBusyId(id);
      try {
        let hint: ClientRfpSessionSummary | undefined;
        setSessionSummaries((prev) => {
          hint = prev.find((s) => s.id === id);
          return prev.map((s) => (s.id === id ? { ...s, archived } : s));
        });
        const { summary: updated, persisted } = await setClientRfpSessionArchived(id, archived, hint);
        setSessionSummaries((prev) =>
          prev.map((s) => (s.id === id ? { ...s, ...updated, archived } : s)),
        );
        if (persisted) {
          const list = await listClientRfpSessions();
          setSessionSummaries(list);
        }
        setStatusHint(
          persisted
            ? archived
              ? "Session archived."
              : "Session restored to Active."
            : archived
              ? "Session archived on this device. Restart scripts/dev-backend.ps1 to sync to the server."
              : "Session restored on this device.",
        );
        if (archived && sessionIdRef.current === id) {
          startNewSession();
        }
        return archived;
      } catch (err) {
        void refreshSessions();
        setStatusHint(err instanceof Error ? err.message : "Could not update archive status.");
        return null;
      } finally {
        setArchiveBusyId(null);
      }
    },
    [refreshSessions, startNewSession],
  );

  const handleProposalInteraction = useCallback(
    (payload: ProposalInteractionPayload) => {
      submitProposalInteraction({
        kind: payload.kind,
        action: payload.action,
        label: payload.label,
        cardPatch: payload.cardPatch ?? null,
        meta: payload.meta ?? {},
      });
    },
    [submitProposalInteraction],
  );

  const subtitleBandActive =
    clientSubtitlesEnabled &&
    (captions.length > 0 || thinking || agentSpeaking || progressText != null);

  const enableVoice = useCallback(async () => {
    await unlockBrowserAudio();
    const pending = pendingSpeechRef.current;
    pendingSpeechRef.current = null;
    setVoiceBlocked(false);
    const testId = appendCaption("agent", "Audio check.", "pending");
    await speakOnce("Audio check.", testId, { mandatory: true });
    if (pending?.text) {
      lastSpokenRef.current = null;
      await speakOnce(pending.text, pending.captionId || undefined, { mandatory: true });
    }
  }, [appendCaption, speakOnce]);

  if (bootstrapping) {
    return (
      <div className="flex h-full min-h-[50vh] items-center justify-center text-sm client-hint-muted">
        Checking your session…
      </div>
    );
  }

  if (!authed) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div
      className={`relative isolate h-full min-h-0 ${proposalPresentation ? "overflow-hidden" : "overflow-y-auto"}`}
      onDragEnter={() => setDragging(true)}
      onDragLeave={() => setDragging(false)}
    >
      {!proposalPresentation && <ParticleConstellation />}
      {proposalPresentation && proposalHtml ? (
        <ProposalTemplateRenderer
          html={proposalHtml}
          variant="background"
          onProposalInteraction={handleProposalInteraction}
        />
      ) : (
        <>
      <div className="relative z-10 flex min-h-full">
        <main
          className={`flex-1 flex flex-col items-center justify-center min-h-[calc(100vh-6rem)] w-full transition-[padding] duration-300 ${
            subtitleBandActive ? "pb-56" : "pb-40"
          }`}
        >
          <CentralVoiceOrb
            levels={micLevels}
            debateRings={debateRings}
            agentSpeaking={agentSpeaking}
            thinking={thinking}
            voiceMode={voiceMode}
            micPhase={micPhase}
            onVoiceToggle={toggleVoiceMode}
          />
          {voiceBlocked && (
            <button
              type="button"
              className="mt-6 text-sm px-4 py-2 rounded-full bg-cyan-500/90 text-slate-950 font-medium"
              onClick={() => void enableVoice()}
            >
              Enable voice
            </button>
          )}
          {agentSpeaking && (
            <button
              type="button"
              className="mt-6 text-sm px-4 py-1 rounded-full border border-amber-400/50 text-amber-200 hover:bg-amber-400/10"
              onClick={() => {
                stopSpeaking();
                lastSpokenRef.current = null;
              }}
            >
              Stop speaking
            </button>
          )}
        </main>
      </div>
      {showSummaryDeck && (
        <AgentCardDeck
          cards={cards}
          clientSession={clientSession}
          saveState={cardSaveState}
          cardError={cardValidationError}
          onPatch={submitCardMutation}
          onMarkSaving={markCardSaving}
        />
      )}
      {agentUiComponent?.type === "availability_table" ? (
        <AgentAvailabilityTable
          dockSide={dockSideForGenerative}
          title={agentUiComponent.title}
          caption={agentUiComponent.caption}
          columns={agentUiComponent.columns}
          rows={agentUiComponent.rows}
          highlights={agentUiComponent.highlights}
          selectedDateIso={selectedAvailabilityIso}
          onSelectRow={(row) => {
            const iso = String(row.date_iso || "");
            const label = String(row.date_label || iso);
            setSelectedAvailabilityIso(iso);
            void askAssistant(`We would like to arrive on ${label}. Please hold that date.`);
          }}
        />
      ) : null}
        </>
      )}
      {authed && !proposalPresentation ? (
        <ClientSessionHistoryRail
          sessions={sessionSummaries}
          activeSessionId={sessionId}
          loading={sessionsLoading}
          composerOpen={composerOpen}
          archiveBusyId={archiveBusyId}
          onSelect={(id) => void activateSession(id)}
          onArchive={handleArchiveSession}
        />
      ) : null}
      <div
        className={`fixed inset-x-0 z-40 flex flex-col items-center px-4 pointer-events-none ${
          proposalPresentation ? "bottom-[5.5rem]" : composerOpen ? "bottom-[7.25rem]" : "bottom-14"
        }`}
      >
        <div
          className={`w-full max-w-xl flex flex-col items-center gap-2 ${
            proposalPresentation ? "pointer-events-none" : "pointer-events-auto"
          }`}
        >
          {clientSubtitlesEnabled ? (
            <VoiceAgentSubtitles
              lines={captions}
              agentSpeaking={agentSpeaking}
              thinking={thinking}
              progressText={progressText}
            />
          ) : null}
          <p className="text-xs text-center max-w-md">
            {isMicLive ? (
              <span className="client-voice-status client-voice-status--active font-medium">● Listening · browser speech</span>
            ) : micPhase === "paused" && voiceMode ? (
              <span className="client-voice-status font-medium">● Voice mode · paused for reply</span>
            ) : micPhase === "connecting" && voiceMode ? (
              <span className="client-voice-status font-medium">● Starting voice…</span>
            ) : voiceMode ? (
              <span className="client-voice-status font-medium">● Voice mode on</span>
            ) : agentSpeaking ? (
              <span className="client-voice-status client-voice-status--speaking animate-pulse font-medium">● Speaking</span>
            ) : (
              <span className="client-hint-muted">
                {proposalPresentation ? "Proposal view · chat below" : "Tap the orb for voice · speak naturally"}
              </span>
            )}
          </p>
          {statusHint && !agentSpeaking && (
            <p className="client-status-hint text-center text-xs max-w-md">{statusHint}</p>
          )}
          {error && <p className="client-status-error text-center text-xs max-w-md">{error}</p>}
        </div>
      </div>
      <ComposerDock
        open={composerOpen}
        onToggle={() => setComposerOpen((v) => !v)}
        onSend={(text) => void onComposerSend(text)}
        onUpload={uploadFiles}
        onNewSession={startNewSession}
        proposalMode={proposalPresentation}
        onBackFromProposal={exitProposalView}
        showOpenProposal={sessionCompleted && !proposalPresentation}
        onOpenProposal={() => void openProposalView()}
      />
      <WindowDragAndDropOverlay visible={dragging} onDrop={uploadFiles} />
    </div>
  );
}
