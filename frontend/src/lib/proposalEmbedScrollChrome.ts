/** Hide in-iframe scrollbars; parent shell owns scrolling (client proposal embed). */
export const PROPOSAL_EMBED_SCROLL_PORT_CSS =
  "html,body{overflow:hidden!important;height:auto!important;max-height:none!important;" +
  "scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "*::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}" +
  "*::-webkit-scrollbar-button{display:none!important;width:0!important;height:0!important;}";

/** Designer live preview — scroll inside iframe; native bars hidden (studio track overlays parent). */
export const DESIGNER_LIVE_PREVIEW_VIEWPORT_CSS =
  "html{height:100%;margin:0;}body{min-height:100%;margin:0;overflow-x:hidden;overflow-y:auto;" +
  "-webkit-overflow-scrolling:touch;scroll-behavior:smooth;" +
  "scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "body::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}" +
  "body::-webkit-scrollbar-button{display:none!important;width:0!important;height:0!important;}" +
  "html{scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "html::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}";

export function appendProposalScrollPortStyle(doc: string): string {
  const trimmed = (doc || "").trim();
  if (!trimmed || trimmed.includes("data-proposal-scroll-port")) return doc;
  const styleTag = `<style data-proposal-scroll-port>${PROPOSAL_EMBED_SCROLL_PORT_CSS}</style>`;
  if (trimmed.includes("</head>")) {
    return trimmed.replace("</head>", `${styleTag}</head>`);
  }
  return `${styleTag}${trimmed}`;
}
