export type AsrStatus = {
  ready: boolean;
  loading: boolean;
  error?: string | null;
  backend?: string;
};

export async function fetchAsrStatus(): Promise<AsrStatus> {
  const res = await fetch("/api/voice/asr-status/", { credentials: "include" });
  if (!res.ok) {
    throw new Error(`ASR status HTTP ${res.status}`);
  }
  return (await res.json()) as AsrStatus;
}

/** Poll until the inference worker is ready (model loaded in background thread). */
export async function waitForAsrWorkerReady(
  opts: { timeoutMs?: number; intervalMs?: number; signal?: AbortSignal } = {},
): Promise<AsrStatus> {
  const timeoutMs = opts.timeoutMs ?? 600_000;
  const intervalMs = opts.intervalMs ?? 1500;
  const started = Date.now();

  for (;;) {
    if (opts.signal?.aborted) {
      throw new Error("ASR wait cancelled");
    }
    const status = await fetchAsrStatus();
    if (status.error) {
      throw new Error(status.error);
    }
    if (status.ready) {
      return status;
    }
    if (Date.now() - started > timeoutMs) {
      throw new Error("Speech model timed out — check Django logs and network.");
    }
    await new Promise((r) => window.setTimeout(r, intervalMs));
  }
}
