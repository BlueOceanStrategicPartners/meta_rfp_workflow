/** Client-side compile for library thumbnails (mirrors backend SAMPLE_REPLACEMENTS). */
const SAMPLE_REPLACEMENTS: Record<string, string> = {
  "{{client_name}}": "Acme Corporation",
  "{{event_dates}}": "2026-06-01 — 2026-06-04",
  "{{verified_room_blocks}}":
    "<table><tr><th>Date</th><th>Rooms</th></tr><tr><td>2026-06-01</td><td>60 King</td></tr></table>",
  "{{selected_map_svg}}":
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120"><rect x="10" y="10" width="180" height="100" fill="rgba(0,180,255,0.15)" stroke="#0af"/></svg>',
  "{{meeting_space_specs}}": "Grand Ballroom · 250 guests",
  "{{xgboost_quote_breakdown}}": "Floor $42,000 · Target $48,500",
  "{{negotiated_concessions}}": "Complimentary AV upgrade",
  "{{cta_accept_button}}": '<button type="button" class="proposal-cta">Accept Proposal</button>',
};

/** Scaled card previews — no scrollbars inside the iframe document. */
const THUMBNAIL_PREVIEW_SHELL_CSS =
  "html,body{overflow:hidden!important;height:100%!important;max-height:100%!important;}" +
  "*{scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "*::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}" +
  "*::-webkit-scrollbar-thumb,*::-webkit-scrollbar-track,*::-webkit-scrollbar-corner{" +
  "display:none!important;background:transparent!important;width:0!important;height:0!important;" +
  "}";

/**
 * Live preview — scroll happens on the studio shell, not inside the iframe
 * (Windows/Chromium often paints a white track on iframe scrollbars).
 */
const LIVE_PREVIEW_SCROLL_PORT_CSS =
  "html,body{overflow:hidden!important;height:auto!important;max-height:none!important;" +
  "scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "*::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}";

export type CompilePreviewOptions = {
  thumbnail?: boolean;
};

function appendLivePreviewChrome(doc: string): string {
  if (doc.includes("data-studio-live-preview-chrome")) return doc;
  const styleTag = `<style data-studio-live-preview-chrome>${LIVE_PREVIEW_SCROLL_PORT_CSS}</style>`;
  let out = doc;
  if (out.includes("</head>")) {
    out = out.replace("</head>", `${styleTag}</head>`);
  } else {
    out = `${styleTag}${out}`;
  }
  return out;
}

/** Inject live-preview scrollbar chrome into server-compiled HTML. */
export function applyLivePreviewDocumentChrome(doc: string): string {
  const trimmed = (doc || "").trim();
  if (!trimmed) return doc;
  return appendLivePreviewChrome(trimmed);
}

export function compileLocalTemplatePreview(
  html: string,
  css: string,
  js: string,
  options?: CompilePreviewOptions,
): string {
  let body = (html || "").trim();
  if (!body) {
    body =
      '<div style="padding:1.25rem;color:#64748b;font-family:system-ui,sans-serif;font-size:14px;">Empty template — chat with the agent to design.</div>';
  } else {
    for (const [token, value] of Object.entries(SAMPLE_REPLACEMENTS)) {
      body = body.split(token).join(value);
    }
  }
  const baseShell = "html,body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:0;}";
  const styleBlock = css
    ? `<style>${css} ${baseShell}</style>`
    : `<style>${baseShell}</style>`;
  const chromeBlock = options?.thumbnail
    ? `<style data-studio-thumbnail-chrome>${THUMBNAIL_PREVIEW_SHELL_CSS}</style>`
    : "";
  const scriptBlock = js ? `<script>${js}</script>` : "";
  let doc = `<!DOCTYPE html><html><head><meta charset="utf-8">${styleBlock}${chromeBlock}</head><body>${body}${scriptBlock}</body></html>`;
  if (!options?.thumbnail) {
    doc = appendLivePreviewChrome(doc);
  }
  return doc;
}
