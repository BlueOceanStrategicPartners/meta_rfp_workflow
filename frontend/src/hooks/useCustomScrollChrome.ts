import { useCallback, useEffect, useState, type RefObject } from "react";

const TRACK_CAP_PX = 12;

export type CustomScrollChrome = {
  canScroll: boolean;
  thumbHeight: number;
  thumbTop: number;
  scrollToPointer: (clientY: number, trackEl: HTMLDivElement) => void;
  remeasure: () => void;
};

export function useCustomScrollChrome(
  viewportRef: RefObject<HTMLElement | null>,
  deps: unknown[] = [],
): CustomScrollChrome {
  const [metrics, setMetrics] = useState({ scrollTop: 0, scrollHeight: 0, clientHeight: 0 });

  const measure = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;
    setMetrics({
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    });
  }, [viewportRef]);

  useEffect(() => {
    measure();
    const el = viewportRef.current;
    if (!el) return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    el.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      el.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, [measure, viewportRef, ...deps]);

  const { scrollTop, scrollHeight, clientHeight } = metrics;
  const canScroll = scrollHeight > clientHeight + 2;
  const trackInner = Math.max(0, clientHeight - TRACK_CAP_PX * 2);
  const thumbMin = 32;
  const thumbHeight = canScroll
    ? Math.max(thumbMin, Math.round((clientHeight / scrollHeight) * trackInner))
    : 0;
  const maxScroll = Math.max(1, scrollHeight - clientHeight);
  const maxThumbTravel = Math.max(0, trackInner - thumbHeight);
  const thumbTop = TRACK_CAP_PX + (scrollTop / maxScroll) * maxThumbTravel;

  const scrollToPointer = (clientY: number, trackEl: HTMLDivElement) => {
    const el = viewportRef.current;
    if (!el || !canScroll) return;
    const rect = trackEl.getBoundingClientRect();
    const y = clientY - rect.top - TRACK_CAP_PX - thumbHeight / 2;
    const ratio = Math.max(0, Math.min(1, y / maxThumbTravel));
    el.scrollTop = ratio * maxScroll;
  };

  return { canScroll, thumbHeight, thumbTop, scrollToPointer, remeasure: measure };
}
