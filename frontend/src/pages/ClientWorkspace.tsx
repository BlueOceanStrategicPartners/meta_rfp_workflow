import { useCallback, useEffect, useRef, useState } from "react";
import ParticleConstellation from "../components/canvas3d/ParticleConstellation";
import CentralVoiceOrb from "../components/canvas3d/CentralVoiceOrb";
import ComposerDock from "../components/composer/ComposerDock";
import WindowDragAndDropOverlay from "../components/composer/WindowDragAndDropOverlay";
import AgentCardDeck from "../components/generative_ui/AgentCardDeck";
import SidePanelVenueMap from "../components/generative_ui/SidePanelVenueMap";
import VenueMapToggleButton from "../components/generative_ui/VenueMapToggleButton";
import ProposalTemplateRenderer from "../components/generative_ui/ProposalTemplateRenderer";
import VoiceAgentSubtitles, { type CaptionLine } from "../components/voice/VoiceAgentSubtitles";
import { useVoiceOrbAudio } from "../hooks/useVoiceOrbAudio";
import { useMuseVoiceTranscribe } from "../hooks/useMuseVoiceTranscribe";
import { useBidirectionalAgentUI } from "../hooks/useBidirectionalAgentUI";
import { unlockBrowserAudio, primeAudioSync, useSeamlessM4TV2 } from "../hooks/useSeamlessM4TV2";
import { cardsHaveExtraction, quickVoiceAck, shouldStartAutonomousPipeline } from "../lib/rfpFlow";
import { createRfpSession, fetchRfpCards, waitForRfpCards } from "../lib/rfpApi";
import { streamAssistantReply } from "../lib/voiceChatStream";
import { fetchPublishedVenueMap, type MapLocation } from "../lib/mapStudioApi";

function newCaptionId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function ClientWorkspace() {
  const [composerOpen, setComposerOpen] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [publishedMapHtml, setPublishedMapHtml] = useState("");
  const [publishedLocations, setPublishedLocations] = useState<MapLocation[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  sessionIdRef.current = sessionId;
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [voiceBlocked, setVoiceBlocked] = useState(false);
  const [statusHint, setStatusHint] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [progressText, setProgressText] = useState<string | null>(null);
  const [captions, setCaptions] = useState<CaptionLine[]>([]);
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
    (captionId: string, durationMs = 1200) => {
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
    () => setAgentSpeaking(true),
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

  const { cards, mapHighlights, proposalHtml, debateRings, error, submitCardMutation, setCards } =
    useBidirectionalAgentUI(sessionId, handleAgentUtterance);

  const ensureSession = useCallback(
    async (
      userMessage: string,
      runDebate: boolean,
      onProgress?: (message: string) => void,
    ): Promise<{ id: string; created: boolean; voiceIntro?: string } | { error: string }> => {
      onProgress?.("Checking your RFP session…");
      if (sessionIdRef.current) {
        const hydrated = await waitForRfpCards(sessionIdRef.current);
        if (cardsHaveExtraction(hydrated)) {
          setCards(hydrated);
        }
        return { id: sessionIdRef.current, created: false };
      }
      onProgress?.("Creating your draft and running venue analysis…");
      const created = await createRfpSession(userMessage, runDebate);
      if (!created.ok) return { error: created.message };
      setSessionId(created.id);
      sessionIdRef.current = created.id;
      if (runDebate) {
        if (cardsHaveExtraction(created.cards)) {
          setCards(created.cards);
        } else {
          onProgress?.("Pulling room block, meeting space, and pricing cards…");
          const hydrated = await waitForRfpCards(created.id);
          if (cardsHaveExtraction(hydrated)) {
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
    [setCards],
  );

  useEffect(() => {
    fetchPublishedVenueMap()
      .then((data) => {
        if (!data) return;
        setPublishedMapHtml(data.compiled_html);
        setPublishedLocations(data.locations || []);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId || cardsHaveExtraction(cards)) return;
    let cancelled = false;
    void waitForRfpCards(sessionId).then((next) => {
      if (!cancelled && cardsHaveExtraction(next)) {
        setCards(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId, cards, setCards]);

  const askAssistant = useCallback(
    async (userMessage: string, opts?: { skipUserCaption?: boolean }) => {
      if (!opts?.skipUserCaption) {
        appendCaption("user", userMessage);
      }
      setThinking(true);
      setProgressText(quickVoiceAck(userMessage));
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
        const startPipeline =
          shouldStartAutonomousPipeline(userMessage) &&
          (!sessionIdRef.current || cardsHaveExtraction(cards));

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
          const line =
            session.voiceIntro ||
            "I've opened a draft summary on the right. Review it, then say approve or negotiate.";
          touchAgentLine(line, "pending");
          await speakOnce(line, agentCaptionId!, { mandatory: true });
          return;
        }

        const reply = await streamAssistantReply(userMessage, sessionIdRef.current, {
          onStatus: (text) => touchAgentLine(text),
          onToken: (token) => {
            streamedText += token;
            touchAgentLine(streamedText.trim());
          },
          onDone: (finalReply) => {
            streamedText = finalReply;
            touchAgentLine(finalReply, "pending");
          },
          onError: (message) => {
            touchAgentLine(message, "pending");
          },
        });

        if (userMessage.toLowerCase().includes("map") || userMessage.toLowerCase().includes("ballroom")) {
          setMapOpen(true);
        }
        const captionId = agentCaptionId ?? appendCaption("agent", reply, "pending");
        if (!agentCaptionId) agentCaptionId = captionId;
        patchCaption(captionId, { text: reply, reveal: 1, status: "pending" });
        await speakOnce(reply, captionId, { mandatory: true });

        const sid = sessionIdRef.current;
        if (sid) {
          const fresh = await fetchRfpCards(sid);
          if (Object.keys(fresh).length) setCards(fresh);
        }
      } finally {
        setThinking(false);
        setProgressText(null);
      }
    },
    [appendCaption, cards, ensureSession, patchCaption, speakOnce],
  );

  askAssistantRef.current = askAssistant;

  const { startListening, pauseListening, resumeListening, stopListening, micPhase, isMicLive } =
    useMuseVoiceTranscribe({
    onPartialTranscript: (text) => {
      if (!liveUserCaptionRef.current) {
        liveUserCaptionRef.current = appendCaption("user", text, "speaking");
      } else {
        patchCaption(liveUserCaptionRef.current, { text, reveal: 1, status: "speaking" });
      }
    },
    onTurnPending: () => {
      setStatusHint("Still listening — pause briefly when you're done speaking.");
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
      primeAudioSync();
      pauseListeningRef.current();
      void unlockBrowserAudio().then(() =>
        askAssistantRef.current(trimmed, { skipUserCaption: true }),
      );
    },
    onError: (message) => {
      setStatusHint(message);
      const fatal =
        /denied|failed to load|port 8000|Could not connect/i.test(message);
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
        const deck = cardsHaveExtraction(created.cards)
          ? created.cards
          : await waitForRfpCards(created.id);
        if (cardsHaveExtraction(deck)) {
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
    [appendCaption, setCards, speakOnce, synthesizePulse],
  );

  const onComposerSend = useCallback(
    (text: string) => {
      primeAudioSync();
      void unlockBrowserAudio().then(async () => {
        synthesizePulse();
        await askAssistant(text);
      });
    },
    [askAssistant, synthesizePulse],
  );

  const showCardDeck = sessionId && cardsHaveExtraction(cards);

  const subtitleBandActive =
    captions.length > 0 || thinking || agentSpeaking || progressText != null;

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

  return (
    <div
      className="relative isolate h-full min-h-0 overflow-y-auto"
      onDragEnter={() => setDragging(true)}
      onDragLeave={() => setDragging(false)}
    >
      <ParticleConstellation />
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
          <VenueMapToggleButton open={mapOpen} onToggle={() => setMapOpen((v) => !v)} />
        </main>
      </div>
      {showCardDeck && <AgentCardDeck cards={cards} onSubmit={submitCardMutation} />}
      <SidePanelVenueMap
        open={mapOpen}
        onClose={() => setMapOpen(false)}
        anchorBottom={composerOpen ? "11.25rem" : "7.5rem"}
        compiledHtml={publishedMapHtml}
        locations={publishedLocations}
        highlights={mapHighlights}
        onSelectZone={() => synthesizePulse()}
      />
      <div
        className={`fixed inset-x-0 z-40 flex flex-col items-center pointer-events-none px-4 ${
          composerOpen ? "bottom-[7.25rem]" : "bottom-14"
        }`}
      >
        <div className="pointer-events-auto w-full max-w-xl flex flex-col items-center gap-2">
          <VoiceAgentSubtitles
            lines={captions}
            agentSpeaking={agentSpeaking}
            thinking={thinking}
            progressText={progressText}
          />
          <p className="text-xs text-center max-w-md">
            {isMicLive ? (
              <span className="text-emerald-300 font-medium">● Listening · local ASR</span>
            ) : micPhase === "paused" && voiceMode ? (
              <span className="text-emerald-200/80 font-medium">● Voice mode · paused for reply</span>
            ) : micPhase === "connecting" && voiceMode ? (
              <span className="text-emerald-200/80 font-medium">● Loading Whisper…</span>
            ) : voiceMode ? (
              <span className="text-emerald-200/80 font-medium">● Voice mode on</span>
            ) : agentSpeaking ? (
              <span className="text-cyan-300 animate-pulse font-medium">● Speaking</span>
            ) : (
              <span className="text-white/40">Tap the orb for voice · Whisper</span>
            )}
          </p>
          {statusHint && !agentSpeaking && (
            <p className="text-xs text-amber-200/90 text-center max-w-md">{statusHint}</p>
          )}
          {error && <p className="text-xs text-orange-300/90 text-center max-w-md">{error}</p>}
        </div>
      </div>
      <ComposerDock
        open={composerOpen}
        onToggle={() => setComposerOpen((v) => !v)}
        onSend={(text) => void onComposerSend(text)}
        onUpload={uploadFiles}
      />
      <WindowDragAndDropOverlay visible={dragging} onDrop={uploadFiles} />
      {proposalHtml && <ProposalTemplateRenderer html={proposalHtml} />}
    </div>
  );
}
