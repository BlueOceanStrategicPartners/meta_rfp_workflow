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

export function compileLocalTemplatePreview(
  html: string,
  css: string,
  js: string
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
  const styleBlock = css
    ? `<style>${css} html,body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:0;}</style>`
    : "<style>html,body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:0;}</style>";
  const scriptBlock = js ? `<script>${js}</script>` : "";
  return `<!DOCTYPE html><html><head><meta charset="utf-8">${styleBlock}</head><body>${body}${scriptBlock}</body></html>`;
}
