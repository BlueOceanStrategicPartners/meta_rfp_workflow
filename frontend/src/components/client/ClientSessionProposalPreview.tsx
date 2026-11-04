import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { buildIsolatedProposalDocument } from "../../lib/proposalIframeDocument";
import { renderClientProposal } from "../../lib/rfpApi";

const previewHtmlCache = new Map<string, string>();

/** Logical width of the rendered proposal page used for thumbnail scaling. */
const PROPOSAL_PAGE_WIDTH = 820;
const PROPOSAL_PAGE_HEIGHT = 1060;

type Props = {
  sessionId: string;
  fallback: ReactNode;
};

/** Scaled iframe thumbnail of the rendered proposal for session history cards. */
export default function ClientSessionProposalPreview({ sessionId, fallback }: Props) {
  const [rawHtml, setRawHtml] = useState<string | null>(() => previewHtmlCache.get(sessionId) ?? null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(() =>
    previewHtmlCache.has(sessionId) ? "ready" : "idle",
  );
  const [scale, setScale] = useState(0.28);
  const viewportRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (previewHtmlCache.has(sessionId)) {
      setRawHtml(previewHtmlCache.get(sessionId)!);
      setStatus("ready");
      return;
    }
    let cancelled = false;
    setStatus("loading");
    void renderClientProposal(sessionId).then((html) => {
      if (cancelled) return;
      if (!html) {
        setStatus("error");
        return;
      }
      previewHtmlCache.set(sessionId, html);
      setRawHtml(html);
      setStatus("ready");
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

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
  }, [status]);

  const srcDoc = useMemo(
    () => (rawHtml ? buildIsolatedProposalDocument(rawHtml, "", "thumbnail") : ""),
    [rawHtml],
  );

  useEffect(() => {
    const el = iframeRef.current;
    if (!el || !srcDoc) return;
    el.srcdoc = srcDoc;
  }, [srcDoc]);

  if (status === "error") return <>{fallback}</>;

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
  if (sessionId) previewHtmlCache.delete(sessionId);
  else previewHtmlCache.clear();
}
