import { useCallback, useEffect, useRef, useState } from "react";

import {
  buildPcmFrame,
  floatToPcm16,
  getCaptureAudioContext,
  int16ToBytes,
  PCM_FRAME_MS,
  PCM_SAMPLES_PER_FRAME,
  primeAudioSync,
  resumeCaptureContext,
} from "../lib/audioEngine";
import { waitForAsrWorkerReady } from "../lib/asrStatus";

/** Wait after ASR end-of-turn before sending to the assistant (allows mid-sentence pauses). */
const TURN_COMMIT_DEBOUNCE_MS = 2000;

export type MuseTranscribeState = "idle" | "connecting" | "listening" | "error";
export type MicPhase = "idle" | "connecting" | "live" | "paused" | "error";

type Options = {
  onFinalTranscript: (text: string) => void;
  onPartialTranscript?: (text: string) => void;
  /** Fired while waiting to see if the user continues the same sentence. */
  onTurnPending?: (text: string) => void;
  onError?: (message: string) => void;
  onMicStopped?: () => void;
  onLevels?: (levels: number[]) => void;
};

export function useMuseVoiceTranscribe(options: Options) {
  const [state, setState] = useState<MuseTranscribeState>("idle");
  const [micPhase, setMicPhase] = useState<MicPhase>("idle");
  const optsRef = useRef(options);
  optsRef.current = options;

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const silentOutRef = useRef<GainNode | null>(null);
  const pcmQueueRef = useRef<Int16Array[]>([]);
  const pcmRemainderRef = useRef<Int16Array>(new Int16Array(0));
  const sendTimerRef = useRef<number | null>(null);
  const streamingRef = useRef(false);
  const listeningRef = useRef(false);
  const captureBusyRef = useRef(false);
  const lastLevelsAtRef = useRef(0);
  const wsGenRef = useRef(0);
  const intentionalStopRef = useRef(false);
  const asrReadyRef = useRef(false);
  const turnAccumRef = useRef("");
  const turnCommitTimerRef = useRef<number | null>(null);

  const clearTurnCommitTimer = useCallback(() => {
    if (turnCommitTimerRef.current != null) {
      window.clearTimeout(turnCommitTimerRef.current);
      turnCommitTimerRef.current = null;
    }
  }, []);

  const commitTurnToAssistant = useCallback(() => {
    clearTurnCommitTimer();
    const text = turnAccumRef.current.trim();
    turnAccumRef.current = "";
    if (text) optsRef.current.onFinalTranscript(text);
  }, [clearTurnCommitTimer]);

  const queueTurnSegment = useCallback(
    (segment: string) => {
      const seg = segment.trim();
      if (!seg) return;
      turnAccumRef.current = turnAccumRef.current
        ? `${turnAccumRef.current} ${seg}`.trim()
        : seg;
      clearTurnCommitTimer();
      optsRef.current.onTurnPending?.(turnAccumRef.current);
      turnCommitTimerRef.current = window.setTimeout(
        commitTurnToAssistant,
        TURN_COMMIT_DEBOUNCE_MS,
      );
    },
    [clearTurnCommitTimer, commitTurnToAssistant],
  );

  const stopPcmSender = useCallback(() => {
    streamingRef.current = false;
    if (sendTimerRef.current != null) {
      window.clearTimeout(sendTimerRef.current);
      sendTimerRef.current = null;
    }
  }, []);

  /** Stop audio graph + PCM send; keep MediaStream alive for fast resume after TTS. */
  const stopCapturePipeline = useCallback(() => {
    stopPcmSender();
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    silentOutRef.current?.disconnect();
    processorRef.current = null;
    sourceRef.current = null;
    silentOutRef.current = null;
    pcmQueueRef.current = [];
    pcmRemainderRef.current = new Int16Array(0);
  }, [stopPcmSender]);

  const releaseMicStream = useCallback(() => {
    stopCapturePipeline();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, [stopCapturePipeline]);

  const closeWs = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    if (!ws) return;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      try {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "endStream" }));
        }
      } catch {
        /* ignore */
      }
      ws.close();
    }
  }, []);

  const stopListening = useCallback(() => {
    intentionalStopRef.current = true;
    asrReadyRef.current = false;
    listeningRef.current = false;
    clearTurnCommitTimer();
    turnAccumRef.current = "";
    releaseMicStream();
    closeWs();
    setState("idle");
    setMicPhase("idle");
  }, [clearTurnCommitTimer, closeWs, releaseMicStream]);

  const pauseListening = useCallback(() => {
    stopCapturePipeline();
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: "pauseCapture" }));
      } catch {
        /* ignore */
      }
      setState("listening");
    }
    setMicPhase("paused");
  }, [stopCapturePipeline]);

  useEffect(() => {
    return () => {
      intentionalStopRef.current = true;
      listeningRef.current = false;
      releaseMicStream();
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: "endStream" }));
        } catch {
          /* ignore */
        }
        ws.close();
      }
    };
  }, [releaseMicStream]);

  const startPcmSender = useCallback((ws: WebSocket) => {
    streamingRef.current = true;
    const sendOneFrame = () => {
      if (!streamingRef.current || ws.readyState !== WebSocket.OPEN) return;
      const { frame, remainder } = buildPcmFrame(
        pcmQueueRef.current,
        pcmRemainderRef.current,
        PCM_SAMPLES_PER_FRAME,
      );
      pcmRemainderRef.current = remainder;
      ws.send(int16ToBytes(frame));
      sendTimerRef.current = window.setTimeout(sendOneFrame, PCM_FRAME_MS);
    };
    sendOneFrame();
  }, []);

  const ensureMicStream = useCallback(async (): Promise<MediaStream> => {
    const existing = streamRef.current;
    if (existing?.getAudioTracks().some((t) => t.readyState === "live")) {
      return existing;
    }
    if (existing) {
      existing.getTracks().forEach((t) => t.stop());
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
        sampleRate: { ideal: 48000 },
      },
    });
    streamRef.current = stream;
    return stream;
  }, []);

  const wireCaptureGraph = useCallback(async () => {
    const stream = await ensureMicStream();
    const ctx = getCaptureAudioContext();
    await resumeCaptureContext();
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    const silentOut = ctx.createGain();
    silentOut.gain.value = 0;
    sourceRef.current = source;
    processorRef.current = processor;
    silentOutRef.current = silentOut;

    processor.onaudioprocess = (event) => {
      if (!streamingRef.current) return;
      const input = event.inputBuffer.getChannelData(0);
      const now = performance.now();
      if (now - lastLevelsAtRef.current > 80) {
        lastLevelsAtRef.current = now;
        let sum = 0;
        for (let j = 0; j < input.length; j += 1) sum += Math.abs(input[j]);
        const avg = sum / input.length;
        optsRef.current.onLevels?.(
          Array.from({ length: 24 }, (_, i) =>
            Math.min(1, avg * 10 + Math.sin(i * 0.5) * 0.04),
          ),
        );
      }
      pcmQueueRef.current.push(floatToPcm16(input, ctx.sampleRate));
    };

    source.connect(processor);
    processor.connect(silentOut);
    silentOut.connect(ctx.destination);
    setMicPhase("live");
  }, [ensureMicStream]);

  const beginStreaming = useCallback(
    async (ws: WebSocket) => {
      if (captureBusyRef.current) return;
      captureBusyRef.current = true;
      const reusingMic = Boolean(
        streamRef.current?.getAudioTracks().some((t) => t.readyState === "live"),
      );
      if (!reusingMic) {
        setMicPhase("connecting");
      }
      pcmQueueRef.current = [];
      pcmRemainderRef.current = new Int16Array(0);
      startPcmSender(ws);
      try {
        await wireCaptureGraph();
      } catch (err) {
        optsRef.current.onError?.((err as Error).message || "Microphone access denied.");
        stopListening();
      } finally {
        captureBusyRef.current = false;
      }
    },
    [startPcmSender, stopListening, wireCaptureGraph],
  );

  const openWebSocketRef = useRef<() => void>(() => {});

  const openWebSocket = useCallback(() => {
    const prev = wsRef.current;
    if (prev && prev.readyState !== WebSocket.CLOSED) {
      prev.onclose = null;
      prev.onerror = null;
      prev.onmessage = null;
      try {
        prev.close();
      } catch {
        /* ignore */
      }
    }

    const gen = ++wsGenRef.current;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/asr/`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      if (wsGenRef.current !== gen || wsRef.current !== ws) return;
      try {
        const data = JSON.parse(String(ev.data));
        if (data.type === "loading") {
          setState("connecting");
          setMicPhase("connecting");
          return;
        }
        if (data.type === "ready") {
          if (!listeningRef.current) return;
          asrReadyRef.current = true;
          setState("listening");
          void beginStreaming(ws);
          return;
        }
        if (data.type === "error") {
          setState("error");
          setMicPhase("error");
          const msg = String(data.message || "ASR error");
          optsRef.current.onError?.(
            msg.includes("1008") || msg.includes("real-time")
              ? "Speak steadily — keep voice mode on while you talk."
              : msg,
          );
          stopListening();
          optsRef.current.onMicStopped?.();
          return;
        }
        if (data.type === "turnComplete") {
          const text = String(data.text || "").trim();
          if (text) queueTurnSegment(text);
          return;
        }
        if (data.type === "speechStart") {
          clearTurnCommitTimer();
          return;
        }
        if (data.type === "transcript") {
          const text = String(data.text || "").trim();
          if (!text) return;
          if (data.final) {
            // Endpointing uses turnComplete; ignore early finals from cloud ASR.
            return;
          }
          optsRef.current.onPartialTranscript?.(text);
        }
      } catch {
        /* ignore */
      }
    };

    ws.onerror = () => {
      if (wsGenRef.current !== gen || wsRef.current !== ws) return;
      if (!listeningRef.current) return;
      setState("error");
      setMicPhase("error");
      optsRef.current.onError?.(
        "Could not connect to speech recognition. Is Django running on port 8000?",
      );
      stopListening();
      optsRef.current.onMicStopped?.();
    };

    ws.onclose = (ev) => {
      if (wsGenRef.current !== gen) return;
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      if (intentionalStopRef.current || !listeningRef.current) {
        releaseMicStream();
        setState("idle");
        setMicPhase("idle");
        return;
      }
      if (!asrReadyRef.current) {
        optsRef.current.onError?.(
          "Speech recognition disconnected before ready. Wait for the model to finish loading, then tap the orb again.",
        );
        stopListening();
        optsRef.current.onMicStopped?.();
        return;
      }
      if (ev.code === 1008) {
        optsRef.current.onError?.(
          "Speech recognition closed — stay in voice mode and speak in a steady stream.",
        );
        optsRef.current.onMicStopped?.();
        listeningRef.current = false;
        asrReadyRef.current = false;
        releaseMicStream();
        setState("idle");
        setMicPhase("idle");
        return;
      }
      setState("connecting");
      setMicPhase("connecting");
      window.setTimeout(() => {
        if (!listeningRef.current || intentionalStopRef.current) return;
        openWebSocketRef.current();
      }, 1500);
    };
  }, [beginStreaming, clearTurnCommitTimer, queueTurnSegment, releaseMicStream, stopListening]);

  openWebSocketRef.current = openWebSocket;

  const startListening = useCallback(async () => {
    if (listeningRef.current && wsRef.current?.readyState === WebSocket.OPEN) return;
    intentionalStopRef.current = false;
    asrReadyRef.current = false;
    listeningRef.current = true;
    setState("connecting");
    setMicPhase("connecting");
    primeAudioSync();
    await resumeCaptureContext();
    try {
      await waitForAsrWorkerReady();
    } catch (err) {
      if (!listeningRef.current) return;
      optsRef.current.onError?.((err as Error).message || "OmniASR worker not ready.");
      stopListening();
      optsRef.current.onMicStopped?.();
      return;
    }
    if (!listeningRef.current || intentionalStopRef.current) return;
    openWebSocket();
  }, [openWebSocket, stopListening]);

  const resumeListening = useCallback(async () => {
    if (!listeningRef.current) {
      return startListening();
    }
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      primeAudioSync();
      await resumeCaptureContext();
      await beginStreaming(ws);
      return;
    }
    if (ws?.readyState === WebSocket.CONNECTING) {
      setMicPhase("connecting");
      return;
    }
    listeningRef.current = false;
    closeWs();
    return startListening();
  }, [beginStreaming, closeWs, startListening]);

  return {
    state,
    micPhase,
    startListening,
    pauseListening,
    resumeListening,
    stopListening,
    isListening: state === "listening",
    isMicLive: micPhase === "live",
  };
};
