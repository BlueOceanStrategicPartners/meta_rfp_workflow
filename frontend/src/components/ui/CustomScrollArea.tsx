import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

export type ScrollEdgeState = {
  canScroll: boolean;
  atTop: boolean;
  atBottom: boolean;
};

type Props = {
  className?: string;
  contentClassName?: string;
  children: ReactNode;
  onScrollEdges?: (state: ScrollEdgeState) => void;
  /** Optional ref to the scrolling viewport (for programmatic scroll, e.g. proposal section nav). */
  viewportRef?: RefObject<HTMLDivElement | null>;
};

const TRACK_CAP_PX = 12;

/** Native scrollbar hidden; faux track with transparent top/bottom corners (theme via CSS vars). */
export default function CustomScrollArea({
  className = "",
  contentClassName = "",
  children,
  onScrollEdges,
  viewportRef: externalViewportRef,
}: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [metrics, setMetrics] = useState({ scrollTop: 0, scrollHeight: 0, clientHeight: 0 });

  const measure = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;
    const scrollTop = el.scrollTop;
    const scrollHeight = el.scrollHeight;
    const clientHeight = el.clientHeight;
    setMetrics({ scrollTop, scrollHeight, clientHeight });
    if (onScrollEdges) {
      const canScroll = scrollHeight > clientHeight + 2;
      onScrollEdges({
        canScroll,
        atTop: scrollTop <= 2,
        atBottom: scrollTop + clientHeight >= scrollHeight - 2,
      });
    }
  }, [onScrollEdges]);

  useEffect(() => {
    measure();
    const el = viewportRef.current;
    if (!el) return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);
    el.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      el.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, [measure, children]);

  useEffect(() => {
    if (!externalViewportRef) return;
    externalViewportRef.current = viewportRef.current;
  });

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

  return (
    <div className={`client-custom-scroll ${className}`.trim()}>
      <div ref={viewportRef} className={`client-custom-scroll__viewport ${contentClassName}`.trim()}>
        {children}
      </div>
      {canScroll ? (
        <div
          className="client-custom-scroll__track"
          role="presentation"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            scrollToPointer(e.clientY, e.currentTarget);
          }}
          onPointerMove={(e) => {
            if (e.buttons !== 1) return;
            scrollToPointer(e.clientY, e.currentTarget);
          }}
        >
          <div
            className="client-custom-scroll__thumb"
            style={{ height: thumbHeight, top: thumbTop }}
          />
        </div>
      ) : null}
    </div>
  );
}
