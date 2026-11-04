import { useEffect, useState, type RefObject } from "react";
import {
  DESIGNER_LIVE_PREVIEW_VIEWPORT_CSS,
  PROPOSAL_EMBED_SCROLL_PORT_CSS,
} from "../lib/proposalEmbedScrollChrome";

export type LivePreviewScrollMode = "embed" | "viewport";

const EMBED_SCROLL_PORT_STYLE = PROPOSAL_EMBED_SCROLL_PORT_CSS;
const VIEWPORT_SCROLL_STYLE = DESIGNER_LIVE_PREVIEW_VIEWPORT_CSS;

function injectPreviewStyle(doc: Document, mode: LivePreviewScrollMode) {
  const attr = mode === "embed" ? "data-studio-scroll-port" : "data-studio-viewport-scroll";
  if (doc.querySelector(`[${attr}]`)) return;
  const el = doc.createElement("style");
  el.setAttribute(attr, "1");
  el.textContent = mode === "embed" ? EMBED_SCROLL_PORT_STYLE : VIEWPORT_SCROLL_STYLE;
  doc.head.appendChild(el);
}

const FLATTENED_FLAG = "data-studio-scroll-flattened";

/** Expand nested scroll containers so the studio shell owns scrolling (no white iframe tracks). */
function flattenInternalScrollContainers(doc: Document) {
  const root = doc.documentElement;
  if (root.getAttribute(FLATTENED_FLAG) === "1") return;
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
  root.setAttribute(FLATTENED_FLAG, "1");
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

const MAX_PREVIEW_IFRAME_HEIGHT_PX = 24_000;

function syncEmbedPreviewIframe(doc: Document): number {
  injectPreviewStyle(doc, "embed");
  flattenInternalScrollContainers(doc);
  const measured = measurePreviewHeight(doc);
  return Math.min(measured, MAX_PREVIEW_IFRAME_HEIGHT_PX);
}

function syncViewportPreviewIframe(doc: Document) {
  injectPreviewStyle(doc, "viewport");
}

/**
 * embed — parent scrolls; iframe grows to content (client proposal embed).
 * viewport — iframe fills panel; document scrolls inside (designer live preview).
 */
export function useLivePreviewIframeScrollPort(
  iframeRef: RefObject<HTMLIFrameElement | null>,
  srcDoc: string,
  mode: LivePreviewScrollMode = "embed",
): number | undefined {
  const [height, setHeight] = useState<number | undefined>(undefined);

  useEffect(() => {
    setHeight(undefined);
    const iframe = iframeRef.current;
    if (!iframe || !srcDoc.trim()) return;

    let observer: ResizeObserver | undefined;
    let raf = 0;
    let debounceTimer = 0;
    let lastHeight = 0;

    const sync = () => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) return;
        if (mode === "viewport") {
          syncViewportPreviewIframe(doc);
          return;
        }
        const next = syncEmbedPreviewIframe(doc);
        if (Math.abs(next - lastHeight) < 2) return;
        lastHeight = next;
        setHeight(next);
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn("[designer] preview iframe height sync failed", err);
        }
      }
    };

    const scheduleSync = () => {
      if (debounceTimer) window.clearTimeout(debounceTimer);
      debounceTimer = window.setTimeout(() => {
        debounceTimer = 0;
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          raf = 0;
          sync();
        });
      }, 80);
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
      if (debounceTimer) window.clearTimeout(debounceTimer);
    };
  }, [iframeRef, srcDoc, mode]);

  return mode === "embed" ? height : undefined;
}
