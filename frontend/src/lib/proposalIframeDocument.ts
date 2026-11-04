import { appendProposalScrollPortStyle } from "./proposalEmbedScrollChrome";
import { isolateProposalEmbedNavigation } from "./proposalPreviewNavigation";

export type ProposalDocumentVariant = "client" | "thumbnail";

/** Server-compiled full HTML — isolate in iframe so client portal theme/CSS cannot leak in. */
export function buildIsolatedProposalDocument(
  html: string,
  extraCss = "",
  variant: ProposalDocumentVariant = "client",
): string {
  let doc = (html || "").trim();
  if (!doc) {
    return '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body></body></html>';
  }

  const padStyle =
    variant === "thumbnail"
      ? '<style id="client-proposal-thumb-pad">html,body{margin:0;padding:0;overflow:hidden;height:100%;width:100%;background:#0a0c12;}body{pointer-events:none;}*{box-sizing:border-box;}</style>'
      : '<style id="client-proposal-iframe-pad">html,body{margin:0;min-height:100%;}body{padding-bottom:6.5rem;box-sizing:border-box;}</style>';
  const extra = extraCss ? `<style>${extraCss}</style>` : "";

  if (!/^<!DOCTYPE/i.test(doc) && !/<html[\s>]/i.test(doc)) {
    doc = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">${padStyle}${extra}</head><body>${doc}</body></html>`;
  } else if (doc.includes("</head>")) {
    doc = doc.replace("</head>", `${padStyle}${extra}</head>`);
  }

  if (variant === "client") {
    doc = isolateProposalEmbedNavigation(doc);
    doc = appendProposalScrollPortStyle(doc);
  }
  return doc;
}
