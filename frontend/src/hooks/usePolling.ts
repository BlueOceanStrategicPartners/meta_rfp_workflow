import { useCallback, useEffect, useRef, useState } from "react";

export type PollingState<T> = {
  data: T | null;
  error: unknown;
  /** True only until the first response (success or failure) arrives. */
  loading: boolean;
  /** True while any request is in flight, including background refreshes. */
  refreshing: boolean;
  reload: () => Promise<void>;
};

/**
 * Fetch on mount and, when `intervalMs` > 0, every `intervalMs` while the tab is visible.
 * Pass `intervalMs = 0` to fetch on mount and on `reload()` only.
 * `deps` re-run the fetch (e.g. filters) and clear the old data; stale responses are ignored.
 */
export function usePolling<T>(
  fn: () => Promise<T>,
  intervalMs = 10_000,
  deps: readonly unknown[] = [],
): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);
  const mounted = useRef(true);

  const run = useCallback(async () => {
    const id = ++seq.current;
    setRefreshing(true);
    try {
      const result = await fnRef.current();
      if (!mounted.current || id !== seq.current) return;
      setData(result);
      setError(null);
    } catch (err) {
      if (!mounted.current || id !== seq.current) return;
      setError(err);
    } finally {
      if (mounted.current && id === seq.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Initial fetch and refetch when deps change. Rows for old filters are dropped
  // so a table never shows the previous property's/filter's data as current.
  const firstRun = useRef(true);
  useEffect(() => {
    if (!firstRun.current) {
      setData(null);
      setError(null);
    }
    firstRun.current = false;
    setLoading(true);
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // Background polling, paused while the tab is hidden.
  useEffect(() => {
    if (!intervalMs || intervalMs <= 0) return;
    let timer: number | undefined;
    const start = () => {
      if (timer !== undefined) return;
      timer = window.setInterval(() => {
        if (document.visibilityState === "visible") void run();
      }, intervalMs);
    };
    const stop = () => {
      if (timer !== undefined) window.clearInterval(timer);
      timer = undefined;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        void run();
        start();
      } else {
        stop();
      }
    };
    if (document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [intervalMs, run]);

  return { data, error, loading, refreshing, reload: run };
}
