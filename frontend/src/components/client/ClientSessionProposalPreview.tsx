import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { buildIsolatedProposalDocument } from "../../lib/proposalIframeDocument";
import { renderClientProposal } from "../../lib/rfpApi";

const previewHtmlCache = new Map<string, string>();
const previewInFlight = new Map<string, Promise<string | null>>();

/** Logical width of the rendered proposal page used for thumbnail scaling. */
const PROPOSAL_PAGE_WIDTH = 820;
const PROPOSAL_PAGE_HEIGHT = 1060;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Fetch proposal HTML for session rail thumbnails.
 * Dedupes concurrent requests and retries when render is not ready yet (common race).
 */
async function loadSessionProposalPreviewHtml(sessionId: string, opts?: { bustCache?: boolean }): Promise<string | null> {
  if (opts?.bustCache) previewHtmlCache.delete(sessionId);

  const cached = previewHtmlCache.get(sessionId);
  if (cached) return cached;

  const existing = previewInFlight.get(sessionId);
  if (existing) return existing;

  const task = (async () => {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const html = await renderClientProposal(sessionId);
      if (html) {
        previewHtmlCache.set(sessionId, html);
        return html;
      }
      if (attempt < 4) await sleep(350 + attempt * 250);
    }
    return null;
  })();

  previewInFlight.set(sessionId, task);
  try {
    return await task;
  } finally {
    if (previewInFlight.get(sessionId) === task) {
      previewInFlight.delete(sessionId);
    }
  }
}

type Props = {
  sessionId: string;
  fallback: ReactNode;
};

/** Scaled iframe thumbnail of the rendered proposal for session history cards. */
export default function ClientSessionProposalPreview({ sessionId, fallback }: Props) {
  const [rawHtml, setRawHtml] = useState<string | null>(() => previewHtmlCache.get(sessionId) ?? null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(() =>
    previewHtmlCache.has(sessionId) ? "ready" : "loading",
  );
  const [scale, setScale] = useState(0.28);
  const [retryGen, setRetryGen] = useState(0);
  const [retryExhausted, setRetryExhausted] = useState(false);
  const viewportRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const loadEpoch = useRef(0);
  const autoRetryCount = useRef(0);

  useEffect(() => {
    autoRetryCount.current = 0;
    setRetryExhausted(false);
  }, [sessionId]);

  useEffect(() => {
    const epoch = ++loadEpoch.current;
    const cached = previewHtmlCache.get(sessionId);
    if (cached && retryGen === 0) {
      setRawHtml(cached);
      setStatus("ready");
      return;
    }

    setStatus("loading");
    setRawHtml(null);
    let cancelled = false;

    void loadSessionProposalPreviewHtml(sessionId, { bustCache: retryGen > 0 }).then((html) => {
      if (loadEpoch.current !== epoch) return;
      if (cancelled && !html) return;
      if (!html) {
        if (autoRetryCount.current >= 3) setRetryExhausted(true);
        setStatus("error");
        return;
      }
      autoRetryCount.current = 0;
      setRawHtml(html);
      setStatus("ready");
    });

    return () => {
      cancelled = true;
    };
  }, [sessionId, retryGen]);

  useEffect(() => {
    if (status !== "error") return;
    if (autoRetryCount.current >= 3) return;
    const timer = window.setTimeout(() => {
      autoRetryCount.current += 1;
      setRetryGen((n) => n + 1);
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [status, sessionId]);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const update = () => {
      const w = el.clientWidth;
      if (w > 0) setScale(w / PROPOSAL_PAGE_WIDTH);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [sessionId, status, rawHtml]);

  const srcDoc = useMemo(
    () => (rawHtml ? buildIsolatedProposalDocument(rawHtml, "", "thumbnail") : ""),
    [rawHtml],
  );

  useEffect(() => {
    const el = iframeRef.current;
    if (!el || !srcDoc) return;
    el.srcdoc = srcDoc;
  }, [srcDoc]);

  if (status === "error" && retryExhausted) {
    return <>{fallback}</>;
  }

  return (
    <div className="client-session-proposal-preview overflow-hidden" aria-hidden>
      <div ref={viewportRef} className="client-session-proposal-preview__viewport">
        {status === "loading" ? <div className="client-session-proposal-preview__skeleton" /> : null}
        {srcDoc ? (
          <div
            className="client-session-proposal-preview__scale"
            style={{
              width: PROPOSAL_PAGE_WIDTH,
              height: PROPOSAL_PAGE_HEIGHT,
              transform: `scale(${scale})`,
            }}
          >
            <iframe
              ref={iframeRef}
              title=""
              tabIndex={-1}
              className="client-session-proposal-preview__iframe"
              sandbox="allow-scripts allow-same-origin"
              referrerPolicy="no-referrer"
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function clearSessionProposalPreviewCache(sessionId?: string) {
  if (sessionId) {
    previewHtmlCache.delete(sessionId);
    previewInFlight.delete(sessionId);
  } else {
    previewHtmlCache.clear();
    previewInFlight.clear();
  }
}

export function primeSessionProposalPreviewCache(sessionId: string, html: string) {
  if (!html.trim()) return;
  previewHtmlCache.set(sessionId, html);
}
