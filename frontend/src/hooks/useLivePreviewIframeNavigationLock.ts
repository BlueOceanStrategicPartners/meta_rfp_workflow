import { useEffect, useRef, type RefObject } from "react";
import { proposalEmbedDocumentIsActive } from "../lib/proposalPreviewNavigation";

const APP_ROUTE = /^\/(client|designer|admin)(\/|$)/;

/**
 * If the preview iframe navigates to the host SPA (/client, /designer, …), restore srcdoc.
 * Skips reset while the embedded proposal document (nav guard marker) is still loaded —
 * srcdoc iframes share the parent URL so pathname alone is not reliable.
 */
export function useLivePreviewIframeNavigationLock(
  iframeRef: RefObject<HTMLIFrameElement | null>,
  srcDoc: string,
) {
  const srcDocRef = useRef(srcDoc);
  srcDocRef.current = srcDoc;

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !srcDoc.trim()) return;

    const onLoad = () => {
      const snapshot = srcDocRef.current;
      if (!snapshot) return;
      try {
        const doc = iframe.contentDocument;
        if (proposalEmbedDocumentIsActive(doc)) return;

        const path = iframe.contentWindow?.location?.pathname ?? "";
        if (path === "/" || APP_ROUTE.test(path)) {
          iframe.srcdoc = snapshot;
        }
      } catch {
        /* opaque origin — ignore */
      }
    };

    iframe.addEventListener("load", onLoad);
    return () => iframe.removeEventListener("load", onLoad);
  }, [iframeRef, srcDoc]);
}
