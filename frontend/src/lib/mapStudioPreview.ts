/** Compile interactive map HTML document for preview (mirrors backend compile_interactive_map). */
export function compileLocalMapPreview(html: string, css: string, js: string): string {
  let body = (html || "").trim();
  if (!body) {
    body =
      '<div style="padding:1.25rem;color:#64748b;font-family:system-ui,sans-serif;font-size:14px;">Empty map — upload a floorplan or describe the venue to the Map Agent.</div>';
  }
  const styleBlock = css
    ? `<style>${css} html,body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:0;}</style>`
    : "<style>html,body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:0;}</style>";
  const scriptBlock = js ? `<script>${js}</script>` : "";
  return `<!DOCTYPE html><html><head><meta charset="utf-8">${styleBlock}</head><body>${body}${scriptBlock}</body></html>`;
}
