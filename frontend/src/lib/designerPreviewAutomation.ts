/** Client-side Live preview panel probes (standard DOM APIs — no extra deps). */

export type PreviewAutomationInteraction = {
  action: string;
  ok: boolean;
  detail?: string;
};

export type PreviewAutomationReport = {
  ok: boolean;
  error?: string;
  duration_ms: number;
  viewport: { w: number; h: number };
  scroll: { docHeight: number; canScroll: boolean; trailingGapPx?: number; contentBottom?: number };
  elements: {
    heroVisible: boolean;
    ctaVisible: boolean;
    mapPopupOpenOnLoad: boolean;
    mapZoneCount: number;
  };
  interactions: PreviewAutomationInteraction[];
};

const PROBE_SCRIPT = `
(function () {
  function visible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    var st = getComputedStyle(el);
    if (r.width < 2 || r.height < 2) return false;
    if (st.display === "none" || st.visibility === "hidden") return false;
    if (parseFloat(st.opacity || "1") < 0.05) return false;
    if (el.classList && el.classList.contains("hidden")) return false;
    return true;
  }
  var doc = document.documentElement;
  var body = document.body;
  var docH = Math.max(body.scrollHeight, doc.scrollHeight, 1);
  var hero = document.querySelector("h1, .hero, .proposal-hero, main h1");
  var cta = document.querySelector(".proposal-cta, .proposal-cta *, button.proposal-cta");
  if (!cta) {
    var buttons = document.querySelectorAll("button, a");
    for (var i = 0; i < buttons.length; i++) {
      if (/accept/i.test(buttons[i].textContent || "")) { cta = buttons[i]; break; }
    }
  }
  var popup = document.getElementById("map-popup");
  var popupOpen = popup && visible(popup);
  var zones = document.querySelectorAll("[data-location-id], .zone, button.zone");
  function lastContentBottom() {
    var selectors = "section, footer, header, main, .proposal-cta, .venue-map-proposal, h1";
    var nodes = body.querySelectorAll(selectors);
    var maxB = 0;
    for (var k = 0; k < nodes.length; k++) {
      var node = nodes[k];
      if (!visible(node)) continue;
      var rect = node.getBoundingClientRect();
      var bottom = rect.bottom + window.scrollY;
      if (bottom > maxB) maxB = bottom;
    }
    if (maxB < 8) {
      var all = body.querySelectorAll("*");
      for (var j = 0; j < all.length; j++) {
        var el = all[j];
        if (!visible(el)) continue;
        var t = (el.textContent || "").trim();
        if (t.length < 2 && !el.querySelector("img,svg,canvas,video")) continue;
        var rb = el.getBoundingClientRect().bottom + window.scrollY;
        if (rb > maxB) maxB = rb;
      }
    }
    return maxB;
  }
  var contentBottom = lastContentBottom();
  var trailingGapPx = Math.max(0, Math.round(docH - contentBottom));
  return {
    docHeight: docH,
    contentBottom: contentBottom,
    trailingGapPx: trailingGapPx,
    viewportW: window.innerWidth,
    viewportH: window.innerHeight,
    heroVisible: visible(hero),
    ctaVisible: visible(cta),
    mapPopupOpenOnLoad: !!popupOpen,
    mapZoneCount: zones.length
  };
})();
`;

const SCROLL_SCRIPT = `
(function () {
  var y0 = window.scrollY;
  window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));
  return { scrolledTo: window.scrollY, from: y0 };
})();
`;

const CLICK_ZONE_SCRIPT = `
(function () {
  var el = document.querySelector("[data-location-id], .zone, button.zone");
  if (!el) return { clicked: false, reason: "no zone control" };
  el.click();
  var popup = document.getElementById("map-popup");
  function visible(node) {
    if (!node) return false;
    return !node.classList.contains("hidden") && getComputedStyle(node).display !== "none";
  }
  return { clicked: true, popupVisibleAfter: visible(popup) };
})();
`;

function evalInPreview(doc: Document, script: string): unknown {
  const win = doc.defaultView;
  if (!win) throw new Error("Preview document unavailable");
  return win.eval(script);
}

/** Hidden iframe so scroll/click probes never move the visible Live preview panel. */
function loadHiddenProbeFrame(srcDoc: string): Promise<{ doc: Document; cleanup: () => void }> {
  return new Promise((resolve, reject) => {
    const frame = document.createElement("iframe");
    frame.setAttribute("aria-hidden", "true");
    frame.tabIndex = -1;
    frame.style.cssText =
      "position:fixed;left:-9999px;top:0;width:1280px;height:900px;opacity:0;pointer-events:none;border:0";
    const cleanup = () => {
      frame.remove();
    };
    const deadline = window.setTimeout(() => {
      cleanup();
      reject(new Error("Preview probe iframe load timeout"));
    }, 8000);
    frame.onload = () => {
      window.clearTimeout(deadline);
      const doc = frame.contentDocument;
      if (!doc?.body) {
        cleanup();
        reject(new Error("Preview probe document unavailable"));
        return;
      }
      resolve({ doc, cleanup });
    };
    frame.srcdoc = srcDoc;
    document.body.appendChild(frame);
  });
}

/** Wait for Live preview iframe (or parsed fallback) before DOM probes. */
export function waitForPreviewIframe(
  iframe: HTMLIFrameElement | null,
  timeoutMs = 4000,
): Promise<boolean> {
  return new Promise((resolve) => {
    if (!iframe) {
      resolve(false);
      return;
    }
    const ready = () => {
      const doc = iframe.contentDocument;
      return Boolean(doc?.body && (doc.body.childElementCount > 0 || (doc.body.textContent || "").trim()));
    };
    if (ready()) {
      resolve(true);
      return;
    }
    const deadline = Date.now() + timeoutMs;
    const onLoad = () => resolve(ready());
    iframe.addEventListener("load", onLoad, { once: true });
    const poll = () => {
      if (ready()) {
        iframe.removeEventListener("load", onLoad);
        resolve(true);
        return;
      }
      if (Date.now() >= deadline) {
        iframe.removeEventListener("load", onLoad);
        resolve(false);
        return;
      }
      requestAnimationFrame(poll);
    };
    requestAnimationFrame(poll);
  });
}

function resolvePreviewSrcDoc(
  iframe: HTMLIFrameElement | null,
  previewDocFallback?: string,
): string | null {
  if (previewDocFallback?.trim()) return previewDocFallback;
  const live = iframe?.srcdoc?.trim();
  if (live) return live;
  return null;
}

export async function runPreviewPanelAutomation(
  iframe: HTMLIFrameElement | null,
  previewDocFallback?: string,
): Promise<PreviewAutomationReport> {
  const started = performance.now();
  const interactions: PreviewAutomationInteraction[] = [];

  const fail = (error: string): PreviewAutomationReport => ({
    ok: false,
    error,
    duration_ms: Math.round(performance.now() - started),
    viewport: { w: 0, h: 0 },
    scroll: { docHeight: 0, canScroll: false },
    elements: {
      heroVisible: false,
      ctaVisible: false,
      mapPopupOpenOnLoad: false,
      mapZoneCount: 0,
    },
    interactions,
  });

  const srcDoc = resolvePreviewSrcDoc(iframe, previewDocFallback);
  if (!srcDoc) {
    return fail("Live preview iframe not ready — turn on sample data or wait for preview to load.");
  }

  let probeCleanup: (() => void) | null = null;
  try {
    const { doc, cleanup } = await loadHiddenProbeFrame(srcDoc);
    probeCleanup = cleanup;

    const base = evalInPreview(doc, PROBE_SCRIPT) as Record<string, unknown>;
    const viewport = {
      w: Number(base.viewportW) || 1280,
      h: Number(base.viewportH) || 900,
    };
    const docHeight = Number(base.docHeight) || 0;
    const trailingGapPx = Number(base.trailingGapPx) || 0;
    const contentBottom = Number(base.contentBottom) || 0;
    const elements = {
      heroVisible: Boolean(base.heroVisible),
      ctaVisible: Boolean(base.ctaVisible),
      mapPopupOpenOnLoad: Boolean(base.mapPopupOpenOnLoad),
      mapZoneCount: Number(base.mapZoneCount) || 0,
    };

    if (elements.mapPopupOpenOnLoad) {
      interactions.push({
        action: "map_popup_on_load",
        ok: false,
        detail: "Map popup visible before any zone click",
      });
    }

    let scrollResult: { scrolledTo?: number; from?: number } = {};
    try {
      scrollResult = evalInPreview(doc, SCROLL_SCRIPT) as typeof scrollResult;
      interactions.push({
        action: "scroll_to_bottom",
        ok: true,
        detail: `y ${scrollResult.from ?? 0} → ${scrollResult.scrolledTo ?? 0}`,
      });
    } catch (e) {
      interactions.push({
        action: "scroll_to_bottom",
        ok: false,
        detail: e instanceof Error ? e.message : "scroll failed",
      });
    }

    try {
      const clickResult = evalInPreview(doc, CLICK_ZONE_SCRIPT) as {
        clicked?: boolean;
        popupVisibleAfter?: boolean;
        reason?: string;
      };
      interactions.push({
        action: "click_first_map_zone",
        ok: Boolean(clickResult.clicked),
        detail: clickResult.clicked
          ? `popup after click: ${clickResult.popupVisibleAfter ? "visible" : "hidden"}`
          : clickResult.reason || "no zone",
      });
    } catch (e) {
      interactions.push({
        action: "click_first_map_zone",
        ok: false,
        detail: e instanceof Error ? e.message : "click probe failed",
      });
    }

    const ok = interactions.every((i) => i.ok) && !elements.mapPopupOpenOnLoad;
    return {
      ok,
      duration_ms: Math.round(performance.now() - started),
      viewport,
      scroll: { docHeight, canScroll: docHeight > viewport.h + 40, trailingGapPx, contentBottom },
      elements,
      interactions,
    };
  } catch (e) {
    return fail(e instanceof Error ? e.message : "Preview automation failed");
  } finally {
    probeCleanup?.();
  }
}

export function shouldAttachPreviewAutomation(message: string, includeAudit: boolean): boolean {
  if (includeAudit) return true;
  return /preview|not showing|close button|looks wrong|debug|overlap|map always|why now/i.test(
    message,
  );
}
