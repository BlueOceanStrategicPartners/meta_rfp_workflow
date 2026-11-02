import { useEffect, useState, type RefObject } from "react";

const SCROLL_PORT_STYLE =
  "html,body{overflow:hidden!important;height:auto!important;max-height:none!important;" +
  "scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "*::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}";

function injectScrollPortStyle(doc: Document) {
  if (doc.querySelector("[data-studio-scroll-port]")) return;
  const el = doc.createElement("style");
  el.setAttribute("data-studio-scroll-port", "1");
  el.textContent = SCROLL_PORT_STYLE;
  doc.head.appendChild(el);
}

/** Expand nested scroll containers so the studio shell owns scrolling (no white iframe tracks). */
function flattenInternalScrollContainers(doc: Document) {
  const win = doc.defaultView;
  if (!win) return;
  const nodes = doc.querySelectorAll("body, body *");
  nodes.forEach((node) => {
    if (!(node instanceof win.HTMLElement)) return;
    const st = win.getComputedStyle(node);
    const oy = st.overflowY;
    const o = st.overflow;
    if (oy === "auto" || oy === "scroll" || o === "auto" || o === "scroll") {
      node.style.overflow = "visible";
      node.style.overflowY = "visible";
      node.style.maxHeight = "none";
      if (st.height.endsWith("vh") || st.height.endsWith("%")) {
        node.style.height = "auto";
      }
    }
  });
}

function measurePreviewHeight(doc: Document): number {
  const win = doc.defaultView;
  const de = doc.documentElement;
  const body = doc.body;
  let max = Math.max(de?.scrollHeight ?? 0, body?.scrollHeight ?? 0, de?.offsetHeight ?? 0, 320);
  if (win) {
    doc.querySelectorAll("body *").forEach((node) => {
      if (!(node instanceof win.HTMLElement)) return;
      max = Math.max(max, node.scrollHeight, node.offsetHeight);
    });
  }
  return Math.ceil(max);
}

function syncPreviewIframe(doc: Document): number {
  injectScrollPortStyle(doc);
  flattenInternalScrollContainers(doc);
  return measurePreviewHeight(doc);
}

/** Parent scrolls; iframe grows to content (avoids white OS scroll tracks inside srcDoc). */
export function useLivePreviewIframeScrollPort(
  iframeRef: RefObject<HTMLIFrameElement | null>,
  srcDoc: string,
): number | undefined {
  const [height, setHeight] = useState<number | undefined>(undefined);

  useEffect(() => {
    setHeight(undefined);
    const iframe = iframeRef.current;
    if (!iframe || !srcDoc.trim()) return;

    let observer: ResizeObserver | undefined;
    let raf = 0;

    const sync = () => {
      const doc = iframe.contentDocument;
      if (!doc) return;
      const next = syncPreviewIframe(doc);
      setHeight(next);
    };

    const scheduleSync = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        raf = 0;
        sync();
      });
    };

    const onLoad = () => {
      scheduleSync();
      window.setTimeout(scheduleSync, 50);
      window.setTimeout(scheduleSync, 400);
      const doc = iframe.contentDocument;
      if (doc?.body && typeof ResizeObserver !== "undefined") {
        observer?.disconnect();
        observer = new ResizeObserver(() => scheduleSync());
        observer.observe(doc.body);
        observer.observe(doc.documentElement);
      }
    };

    iframe.addEventListener("load", onLoad);
    if (iframe.contentDocument?.readyState === "complete") onLoad();
    else scheduleSync();

    return () => {
      iframe.removeEventListener("load", onLoad);
      observer?.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [iframeRef, srcDoc]);

  return height;
}
