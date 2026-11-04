/** Hide in-iframe scrollbars; parent shell owns scrolling (matches designer live preview). */
export const PROPOSAL_EMBED_SCROLL_PORT_CSS =
  "html,body{overflow:hidden!important;height:auto!important;max-height:none!important;" +
  "scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "*::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}" +
  "*::-webkit-scrollbar-button{display:none!important;width:0!important;height:0!important;}";

export function appendProposalScrollPortStyle(doc: string): string {
  const trimmed = (doc || "").trim();
  if (!trimmed || trimmed.includes("data-proposal-scroll-port")) return doc;
  const styleTag = `<style data-proposal-scroll-port>${PROPOSAL_EMBED_SCROLL_PORT_CSS}</style>`;
  if (trimmed.includes("</head>")) {
    return trimmed.replace("</head>", `${styleTag}</head>`);
  }
  return `${styleTag}${trimmed}`;
}
