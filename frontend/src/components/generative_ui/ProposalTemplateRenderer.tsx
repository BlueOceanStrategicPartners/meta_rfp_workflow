import { useEffect, useMemo, useRef } from "react";
import { buildIsolatedProposalDocument } from "../../lib/proposalIframeDocument";
import { parseProposalPostMessage, type ProposalInteractionPayload } from "../../lib/proposalClientBridge";
import { useLivePreviewIframeNavigationLock } from "../../hooks/useLivePreviewIframeNavigationLock";
import { useLivePreviewIframeScrollPort } from "../../hooks/useLivePreviewIframeScrollPort";
import CustomScrollArea from "../ui/CustomScrollArea";

type Props = {
  html: string;
  css?: string;
  variant?: "overlay" | "background";
  onProposalInteraction?: (payload: ProposalInteractionPayload) => void;
};

function ProposalIframe({
  srcDoc,
  title,
  className,
  iframeClassName,
  scrollPort,
  scrollViewportRef,
  iframeRef: externalIframeRef,
}: {
  srcDoc: string;
  title: string;
  className?: string;
  iframeClassName?: string;
  scrollPort?: boolean;
  scrollViewportRef?: React.RefObject<HTMLDivElement | null>;
  iframeRef?: React.RefObject<HTMLIFrameElement | null>;
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const mergedIframeRef = externalIframeRef ?? iframeRef;
  const height = useLivePreviewIframeScrollPort(
    scrollPort ? mergedIframeRef : { current: null },
    scrollPort ? srcDoc : "",
  );

  useEffect(() => {
    const el = mergedIframeRef.current;
    if (!el) return;
    el.srcdoc = srcDoc;
  }, [srcDoc, mergedIframeRef]);

  useLivePreviewIframeNavigationLock(mergedIframeRef, srcDoc);

  const iframe = (
    <iframe
      ref={mergedIframeRef}
      title={title}
      className={iframeClassName ?? className}
      sandbox="allow-scripts allow-same-origin"
      referrerPolicy="no-referrer"
      style={scrollPort && height ? { height: `${height}px` } : undefined}
    />
  );

  if (!scrollPort) {
    return iframe;
  }

  return (
    <CustomScrollArea
      className={`proposal-embed-scroll ${className ?? ""}`.trim()}
      contentClassName="min-h-0"
      viewportRef={scrollViewportRef}
    >
      {iframe}
    </CustomScrollArea>
  );
}

export default function ProposalTemplateRenderer({
  html,
  css = "",
  variant = "overlay",
  onProposalInteraction,
}: Props) {
  const srcDoc = useMemo(() => buildIsolatedProposalDocument(html, css), [html, css]);
  const onInteractionRef = useRef(onProposalInteraction);
  onInteractionRef.current = onProposalInteraction;
  const proposalScrollRef = useRef<HTMLDivElement>(null);
  const proposalIframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.source !== proposalIframeRef.current?.contentWindow) return;
      const raw = event.data;
      if (raw && typeof raw === "object" && (raw as { type?: string }).type === "proposal-embed-scroll") {
        const top = (raw as { top?: number }).top;
        const behavior = (raw as { behavior?: string }).behavior === "smooth" ? "smooth" : "auto";
        if (typeof top === "number" && proposalScrollRef.current) {
          proposalScrollRef.current.scrollTo({ top, behavior });
        }
        return;
      }
      if (event.source === null) return;
      const parsed = parseProposalPostMessage(event.data);
      if (parsed) onInteractionRef.current?.(parsed);
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  if (variant === "background") {
    return (
      <div
        className="proposal-iframe-layer fixed inset-0 z-20 flex flex-col bg-transparent pointer-events-auto"
        aria-label="Proposal preview"
      >
        <ProposalIframe
          srcDoc={srcDoc}
          title="Your proposal"
          className="h-full min-h-0 flex-1"
          iframeClassName="proposal-iframe block w-full border-0 bg-transparent pointer-events-auto"
          scrollPort
          scrollViewportRef={proposalScrollRef}
          iframeRef={proposalIframeRef}
        />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/80 p-4 sm:p-8">
      <ProposalIframe
        srcDoc={srcDoc}
        title="Proposal preview"
        className="min-h-0 flex-1"
        iframeClassName="proposal-iframe min-h-0 flex-1 w-full max-w-4xl mx-auto rounded-xl border-0 bg-white shadow-2xl"
        scrollPort
        scrollViewportRef={proposalScrollRef}
        iframeRef={proposalIframeRef}
      />
    </div>
  );
}
