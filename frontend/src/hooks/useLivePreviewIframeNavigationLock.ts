import { useEffect, useRef, type RefObject } from "react";

const APP_ROUTE = /^\/(client|designer|admin)(\/|$)/;

/**
 * If the preview iframe navigates to the host SPA (/client, /designer, …), restore srcdoc.
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
