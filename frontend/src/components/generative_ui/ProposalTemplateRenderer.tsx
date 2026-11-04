import { useEffect, useMemo, useRef } from "react";
import { buildIsolatedProposalDocument } from "../../lib/proposalIframeDocument";
import { parseProposalPostMessage, type ProposalInteractionPayload } from "../../lib/proposalClientBridge";

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
}: {
  srcDoc: string;
  title: string;
  className?: string;
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const el = iframeRef.current;
    if (!el) return;
    el.srcdoc = srcDoc;
  }, [srcDoc]);

  return (
    <iframe
      ref={iframeRef}
      title={title}
      className={className}
      sandbox="allow-scripts allow-same-origin"
      referrerPolicy="no-referrer"
    />
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

  useEffect(() => {
    if (!onProposalInteraction) return;
    const handler = (event: MessageEvent) => {
      if (event.source === null) return;
      const parsed = parseProposalPostMessage(event.data);
      if (parsed) onInteractionRef.current?.(parsed);
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [onProposalInteraction]);

  if (variant === "background") {
    return (
      <div
        className="proposal-iframe-layer fixed inset-0 z-20 flex flex-col bg-transparent pointer-events-auto"
        aria-label="Proposal preview"
      >
        <ProposalIframe
          srcDoc={srcDoc}
          title="Your proposal"
          className="proposal-iframe min-h-0 flex-1 w-full border-0 bg-transparent pointer-events-auto"
        />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/80 p-4 sm:p-8">
      <ProposalIframe
        srcDoc={srcDoc}
        title="Proposal preview"
        className="proposal-iframe min-h-0 flex-1 w-full max-w-4xl mx-auto rounded-xl border-0 bg-white shadow-2xl"
      />
    </div>
  );
}
