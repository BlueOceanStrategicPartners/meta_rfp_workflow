/** Minimal safe markdown: **bold**, `code`, ``` fences */
export function renderDesignerMarkdown(text: string): string {
  let html = escapeHtml(text);
  html = html.replace(/```([\s\S]*?)```/g, (_m, code) =>
    `<pre class="md-pre"><code>${escapeHtml(String(code).trim())}</code></pre>`
  );
  html = html.replace(/`([^`]+)`/g, "<code class='md-code'>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\n/g, "<br/>");
  return html;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
