import { useEffect, useMemo, useRef } from "react";

type Props = {
  html: string;
  css?: string;
  variant?: "overlay" | "background";
};

/** Server-compiled full HTML — isolate in iframe so client portal theme/CSS cannot leak in. */
function buildIsolatedProposalDocument(html: string, extraCss = ""): string {
  let doc = (html || "").trim();
  if (!doc) {
    return "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body></body></html>";
  }

  const padStyle =
    "<style id=\"client-proposal-iframe-pad\">html,body{margin:0;min-height:100%;}body{padding-bottom:6.5rem;box-sizing:border-box;}</style>";
  const extra = extraCss ? `<style>${extraCss}</style>` : "";

  if (!/^<!DOCTYPE/i.test(doc) && !/<html[\s>]/i.test(doc)) {
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">${padStyle}${extra}</head><body>${doc}</body></html>`;
  }

  if (doc.includes("</head>")) {
    return doc.replace("</head>", `${padStyle}${extra}</head>`);
  }
  return doc;
}

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

export default function ProposalTemplateRenderer({ html, css = "", variant = "overlay" }: Props) {
  const srcDoc = useMemo(() => buildIsolatedProposalDocument(html, css), [html, css]);

  if (variant === "background") {
    return (
      <div
        className="proposal-iframe-layer fixed inset-x-0 top-0 bottom-[5.5rem] z-20 flex flex-col bg-black pointer-events-auto"
        aria-label="Proposal preview"
      >
        <ProposalIframe
          srcDoc={srcDoc}
          title="Your proposal"
          className="proposal-iframe min-h-0 flex-1 w-full border-0 bg-black pointer-events-auto"
        />
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 z-[1] h-28 bg-gradient-to-t from-black/90 to-transparent"
          aria-hidden
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
