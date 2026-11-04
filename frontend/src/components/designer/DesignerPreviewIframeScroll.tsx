import { useCallback, useEffect, useState, type ReactNode, type RefObject } from "react";

const TRACK_CAP_PX = 12;

type Props = {
  iframeRef: RefObject<HTMLIFrameElement | null>;
  srcDoc: string;
  className?: string;
  children: ReactNode;
};

type ScrollMetrics = { scrollTop: number; scrollHeight: number; clientHeight: number };

function readIframeScrollMetrics(iframe: HTMLIFrameElement): ScrollMetrics | null {
  const win = iframe.contentWindow;
  const doc = iframe.contentDocument;
  if (!win || !doc) return null;

  const root = doc.documentElement;
  const body = doc.body;
  const scrollHeight = Math.max(
    root?.scrollHeight ?? 0,
    body?.scrollHeight ?? 0,
    root?.offsetHeight ?? 0,
    body?.offsetHeight ?? 0,
  );
  const clientHeight = win.innerHeight || iframe.clientHeight || root?.clientHeight || 0;
  const scrollTop = Math.max(win.scrollY || 0, root?.scrollTop ?? 0, body?.scrollTop ?? 0);

  return { scrollTop, scrollHeight, clientHeight };
}

function scrollIframeTo(iframe: HTMLIFrameElement, top: number) {
  const win = iframe.contentWindow;
  const doc = iframe.contentDocument;
  if (!win || !doc) return;
  try {
    win.scrollTo({ top, behavior: "auto" });
  } catch {
    /* ignore */
  }
  const root = doc.documentElement;
  const body = doc.body;
  if (root) root.scrollTop = top;
  if (body) body.scrollTop = top;
}

/** Studio faux scrollbar synced to preview iframe document scroll (native bar hidden via injected CSS). */
export default function DesignerPreviewIframeScroll({
  iframeRef,
  srcDoc,
  className = "",
  children,
}: Props) {
  const [metrics, setMetrics] = useState<ScrollMetrics>({ scrollTop: 0, scrollHeight: 0, clientHeight: 0 });

  const measure = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const next = readIframeScrollMetrics(iframe);
    if (!next) return;
    setMetrics((prev) =>
      prev.scrollTop === next.scrollTop &&
      prev.scrollHeight === next.scrollHeight &&
      prev.clientHeight === next.clientHeight
        ? prev
        : next,
    );
  }, [iframeRef]);

  useEffect(() => {
    setMetrics({ scrollTop: 0, scrollHeight: 0, clientHeight: 0 });
    const iframe = iframeRef.current;
    if (!iframe || !srcDoc.trim()) return;

    let ro: ResizeObserver | undefined;
    let scrollWin: Window | null = null;
    let debounce = 0;
    let raf = 0;

    const schedule = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        raf = 0;
        measure();
      });
    };

    const bind = () => {
      const win = iframe.contentWindow;
      const doc = iframe.contentDocument;
      if (!win || !doc?.documentElement) return false;

      scrollWin?.removeEventListener("scroll", schedule);
      scrollWin = win;
      win.addEventListener("scroll", schedule, { passive: true, capture: true });
      doc.documentElement.addEventListener("scroll", schedule, { passive: true });
      doc.body?.addEventListener("scroll", schedule, { passive: true });
      win.addEventListener("resize", schedule);

      if (typeof ResizeObserver !== "undefined") {
        ro?.disconnect();
        ro = new ResizeObserver(schedule);
        ro.observe(doc.documentElement);
        if (doc.body) ro.observe(doc.body);
      }

      measure();
      return true;
    };

    const onLoad = () => {
      schedule();
      window.setTimeout(schedule, 80);
      window.setTimeout(schedule, 400);
      window.setTimeout(schedule, 1200);
      if (!bind()) {
        let attempts = 0;
        const retry = () => {
          if (bind() || attempts > 60) return;
          attempts += 1;
          window.setTimeout(retry, 50);
        };
        retry();
      }
    };

    iframe.addEventListener("load", onLoad);
    if (iframe.contentDocument?.readyState === "complete") onLoad();
    else schedule();

    return () => {
      iframe.removeEventListener("load", onLoad);
      scrollWin?.removeEventListener("scroll", schedule, { capture: true });
      iframe.contentDocument?.documentElement.removeEventListener("scroll", schedule);
      iframe.contentDocument?.body?.removeEventListener("scroll", schedule);
      scrollWin?.removeEventListener("resize", schedule);
      ro?.disconnect();
      if (debounce) window.clearTimeout(debounce);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [iframeRef, srcDoc, measure]);

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
    const iframe = iframeRef.current;
    if (!iframe || !canScroll) return;
    const rect = trackEl.getBoundingClientRect();
    const y = clientY - rect.top - TRACK_CAP_PX - thumbHeight / 2;
    const ratio = Math.max(0, Math.min(1, y / maxThumbTravel));
    scrollIframeTo(iframe, ratio * maxScroll);
    measure();
  };

  return (
    <div className={`client-custom-scroll studio-live-preview-iframe-scroll ${className}`.trim()}>
      <div className="client-custom-scroll__viewport studio-live-preview-iframe-scroll__viewport">{children}</div>
      {canScroll ? (
        <div
          className="client-custom-scroll__track studio-live-preview-iframe-scroll__track"
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
