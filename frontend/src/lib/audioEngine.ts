/**
 * Shared browser audio output/input context for TTS and Muse ASR capture.
 */

const SILENT_WAV =
  "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAA==";

export const PCM_TARGET_RATE = 16_000;

let captureContext: AudioContext | null = null;

export function getCaptureAudioContext(): AudioContext {
  if (!captureContext) {
    try {
      captureContext = new AudioContext({ sampleRate: PCM_TARGET_RATE });
    } catch {
      captureContext = new AudioContext();
    }
  }
  return captureContext;
}

export async function resumeCaptureContext(): Promise<void> {
  const ctx = getCaptureAudioContext();
  if (ctx.state === "suspended") {
    await ctx.resume();
  }
}

let sharedContext: AudioContext | null = null;
let outputGain: GainNode | null = null;
let activeSource: AudioBufferSourceNode | null = null;
let activeElement: HTMLAudioElement | null = null;
let activeUtterance: SpeechSynthesisUtterance | null = null;

export function getSharedAudioContext(): AudioContext {
  if (!sharedContext) {
    sharedContext = new AudioContext();
    outputGain = sharedContext.createGain();
    outputGain.gain.value = 1.25;
    outputGain.connect(sharedContext.destination);
  }
  return sharedContext;
}

export function getOutputGain(): GainNode {
  getSharedAudioContext();
  return outputGain!;
}

/** Call synchronously inside a user click/tap handler. */
export function primeAudioSync(): void {
  try {
    const ctx = getSharedAudioContext();
    void ctx.resume();
    const silent = new Audio(SILENT_WAV);
    silent.volume = 0.05;
    void silent.play().catch(() => {});
    if (typeof window !== "undefined" && window.speechSynthesis) {
      void loadSpeechVoices();
    }
  } catch {
    /* ignore */
  }
}

export async function resumeAudioContext(): Promise<void> {
  const ctx = getSharedAudioContext();
  if (ctx.state === "suspended") {
    await ctx.resume();
  }
}

export function stopActivePlayback(): void {
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  activeUtterance = null;
  if (activeSource) {
    try {
      activeSource.onended = null;
      activeSource.stop();
    } catch {
      /* already stopped */
    }
    activeSource.disconnect();
    activeSource = null;
  }
  if (activeElement) {
    activeElement.onended = null;
    activeElement.onerror = null;
    activeElement.pause();
    if (activeElement.src.startsWith("blob:")) {
      URL.revokeObjectURL(activeElement.src);
    }
    activeElement = null;
  }
}

export type PlayBlobResult =
  | { ok: true; duration: number }
  | { ok: false; reason: "play_blocked" | "decode" | "error"; detail?: string };

/** Speak agent text when backend is in fixture tone mode (no Seamless weights loaded). */
function scoreVoice(v: SpeechSynthesisVoice): number {
  const name = v.name.toLowerCase();
  let score = 0;
  if (name.includes("natural")) score += 60;
  if (name.includes("neural")) score += 55;
  if (name.includes("online")) score += 45;
  if (name.includes("premium")) score += 40;
  if (name.includes("aria") || name.includes("jenny") || name.includes("guy")) score += 35;
  if (name.includes("google")) score += 25;
  if (name.includes("samantha")) score += 20;
  if (v.lang.toLowerCase().startsWith("en")) score += 15;
  if (!v.localService) score += 8;
  if (name.includes("zira") || name.includes("david")) score -= 10;
  return score;
}

function loadSpeechVoices(): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    const existing = window.speechSynthesis.getVoices();
    if (existing.length > 0) {
      resolve(existing);
      return;
    }
    const onChange = () => {
      window.speechSynthesis.removeEventListener("voiceschanged", onChange);
      resolve(window.speechSynthesis.getVoices());
    };
    window.speechSynthesis.addEventListener("voiceschanged", onChange);
    window.setTimeout(() => resolve(window.speechSynthesis.getVoices()), 400);
  });
}

async function pickNaturalVoice(): Promise<SpeechSynthesisVoice | null> {
  const voices = await loadSpeechVoices();
  if (!voices.length) return null;
  const ranked = [...voices].sort((a, b) => scoreVoice(b) - scoreVoice(a));
  return ranked[0] ?? null;
}

export async function speakWithSpeechSynthesis(
  text: string,
  onProgress?: (current: number, duration: number) => void,
): Promise<PlayBlobResult> {
  if (typeof window === "undefined" || !window.speechSynthesis) {
    return { ok: false, reason: "error", detail: "Speech synthesis unavailable" };
  }
  stopActivePlayback();
  await resumeAudioContext();

  const cleaned = text.trim();
  if (!cleaned) {
    return { ok: false, reason: "error", detail: "empty text" };
  }

  const voice = await pickNaturalVoice();
  const estimatedDuration = Math.min(120, Math.max(2, cleaned.length * 0.052));

  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(cleaned);
    utterance.lang = voice?.lang || "en-US";
    if (voice) utterance.voice = voice;
    utterance.rate = 0.96;
    utterance.pitch = 1;
    activeUtterance = utterance;
    const startedAt = performance.now();

    const tick = () => {
      if (activeUtterance !== utterance) return;
      const elapsed = (performance.now() - startedAt) / 1000;
      onProgress?.(Math.min(estimatedDuration, elapsed), estimatedDuration);
      if (elapsed < estimatedDuration) {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);

    utterance.onend = () => {
      if (activeUtterance === utterance) activeUtterance = null;
      onProgress?.(estimatedDuration, estimatedDuration);
      resolve({ ok: true, duration: estimatedDuration });
    };
    utterance.onerror = () => {
      if (activeUtterance === utterance) activeUtterance = null;
      resolve({ ok: false, reason: "error", detail: "speechSynthesis error" });
    };

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

/** Prefer HTMLAudioElement (most reliable after user gesture), then Web Audio API. */
export async function playWavBlob(
  blob: Blob,
  onProgress?: (current: number, duration: number) => void,
): Promise<PlayBlobResult> {
  await resumeAudioContext();
  stopActivePlayback();

  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.volume = 1;
  activeElement = audio;

  const htmlResult = await new Promise<PlayBlobResult>((resolve) => {
    const done = (result: PlayBlobResult) => {
      URL.revokeObjectURL(url);
      if (activeElement === audio) activeElement = null;
      resolve(result);
    };

    audio.ontimeupdate = () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        onProgress?.(audio.currentTime, audio.duration);
      }
    };
    audio.onended = () => done({ ok: true, duration: audio.duration || 3 });
    audio.onerror = () => done({ ok: false, reason: "error", detail: "audio element error" });

    audio
      .play()
      .then(() => {})
      .catch((err) => {
        const name = (err as Error).name;
        done({
          ok: false,
          reason: name === "NotAllowedError" ? "play_blocked" : "error",
          detail: name,
        });
      });
  });

  if (htmlResult.ok) {
    return htmlResult;
  }
  if (htmlResult.reason === "play_blocked") {
    return htmlResult;
  }

  const arrayBuffer = await blob.arrayBuffer();
  const ctx = getSharedAudioContext();
  const gain = getOutputGain();

  try {
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(gain);
    activeSource = source;

    const durationSec = audioBuffer.duration || 3;
    const startedAt = ctx.currentTime;

    return await new Promise((resolve) => {
      const finish = (result: PlayBlobResult) => {
        if (activeSource === source) {
          activeSource = null;
        }
        resolve(result);
      };

      source.onended = () => {
        onProgress?.(durationSec, durationSec);
        finish({ ok: true, duration: durationSec });
      };

      try {
        source.start(0);
      } catch (err) {
        finish({ ok: false, reason: "error", detail: (err as Error).message });
        return;
      }

      const tick = () => {
        const elapsed = Math.min(durationSec, ctx.currentTime - startedAt);
        onProgress?.(elapsed, durationSec);
        if (elapsed < durationSec) {
          requestAnimationFrame(tick);
        }
      };
      requestAnimationFrame(tick);
    });
  } catch (err) {
    return { ok: false, reason: "decode", detail: (err as Error).message };
  }
}

export const PCM_FRAME_MS = 80;
export const PCM_BYTES_PER_FRAME = (PCM_TARGET_RATE * 2 * PCM_FRAME_MS) / 1000;
export const PCM_SAMPLES_PER_FRAME = PCM_BYTES_PER_FRAME / 2;

/** Float32 mono at `inputRate` → Int16 PCM at 16 kHz (linear interpolation). */
export function floatToPcm16(input: Float32Array, inputRate: number): Int16Array {
  if (input.length === 0) {
    return new Int16Array(0);
  }
  if (Math.abs(inputRate - PCM_TARGET_RATE) < 1) {
    const out = new Int16Array(input.length);
    for (let i = 0; i < input.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, input[i] || 0));
      out[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return out;
  }

  const outLength = Math.max(1, Math.round((input.length * PCM_TARGET_RATE) / inputRate));
  const out = new Int16Array(outLength);
  for (let i = 0; i < outLength; i += 1) {
    const srcPos = (i * inputRate) / PCM_TARGET_RATE;
    const idx = Math.floor(srcPos);
    const frac = srcPos - idx;
    const s0 = input[Math.min(idx, input.length - 1)] || 0;
    const s1 = input[Math.min(idx + 1, input.length - 1)] || 0;
    const sample = Math.max(-1, Math.min(1, s0 + frac * (s1 - s0)));
    out[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return out;
}

export function int16ToBytes(chunk: Int16Array): ArrayBuffer {
  const buf = new ArrayBuffer(chunk.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < chunk.length; i += 1) {
    view.setInt16(i * 2, chunk[i], true);
  }
  return buf;
}

export function buildPcmFrame(
  queue: Int16Array[],
  remainder: Int16Array,
  samplesPerFrame: number,
): { frame: Int16Array; remainder: Int16Array } {
  let merged = remainder;
  while (merged.length < samplesPerFrame && queue.length > 0) {
    const next = queue.shift()!;
    const combined = new Int16Array(merged.length + next.length);
    combined.set(merged);
    combined.set(next, merged.length);
    merged = combined;
  }
  const frame = new Int16Array(samplesPerFrame);
  frame.set(merged.subarray(0, Math.min(merged.length, samplesPerFrame)));
  const nextRemainder =
    merged.length > samplesPerFrame ? merged.subarray(samplesPerFrame) : new Int16Array(0);
  return { frame, remainder: nextRemainder };
}
