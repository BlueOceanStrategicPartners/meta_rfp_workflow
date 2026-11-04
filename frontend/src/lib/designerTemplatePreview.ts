/** Client-side compile for library thumbnails (mirrors backend JSON binding seed). */
import { compileBindingsInTemplate } from "./proposalBindingSamples";
import { DESIGNER_LIVE_PREVIEW_VIEWPORT_CSS } from "./proposalEmbedScrollChrome";
import { isolateProposalEmbedNavigation } from "./proposalPreviewNavigation";

const PROPOSAL_BINDING_RUNTIME_TAG =
  '<script src="/proposal_binding_runtime.js" data-proposal-binding-runtime="1"></script>';

/** Scaled card previews — no scrollbars inside the iframe document. */
const THUMBNAIL_PREVIEW_SHELL_CSS =
  "html,body{overflow:hidden!important;height:100%!important;max-height:100%!important;}" +
  "*{scrollbar-width:none!important;-ms-overflow-style:none!important;}" +
  "*::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}" +
  "*::-webkit-scrollbar-thumb,*::-webkit-scrollbar-track,*::-webkit-scrollbar-corner{" +
  "display:none!important;background:transparent!important;width:0!important;height:0!important;" +
  "}";

/** Live preview — in-iframe scroll (matches “open in new tab” layout). */
const LIVE_PREVIEW_SCROLL_PORT_CSS = DESIGNER_LIVE_PREVIEW_VIEWPORT_CSS;

export type CompilePreviewOptions = {
  thumbnail?: boolean;
  /** When false, bindings are empty (no seed sample RFP). Default true for library thumbnails. */
  useSampleData?: boolean;
};

function appendProposalBindingRuntime(doc: string): string {
  if (doc.includes("proposalBindingHydrate") || doc.includes("proposal_binding_runtime.js")) {
    return doc;
  }
  const tag = PROPOSAL_BINDING_RUNTIME_TAG;
  if (doc.includes("</body>")) {
    return doc.replace("</body>", `${tag}</body>`);
  }
  return doc + tag;
}

function appendLivePreviewChrome(doc: string): string {
  let out = isolateProposalEmbedNavigation(doc);
  if (!out.includes("data-studio-live-preview-chrome")) {
    const styleTag = `<style data-studio-live-preview-chrome>${LIVE_PREVIEW_SCROLL_PORT_CSS}</style>`;
    if (out.includes("</head>")) {
      out = out.replace("</head>", `${styleTag}</head>`);
    } else {
      out = `${styleTag}${out}`;
    }
  }
  return out;
}

/** Inject live-preview scrollbar chrome into server-compiled HTML. */
export function applyLivePreviewDocumentChrome(doc: string): string {
  const trimmed = (doc || "").trim();
  if (!trimmed) return doc;
  return appendLivePreviewChrome(trimmed);
}

const TAILWIND_CDN = '<script src="https://cdn.tailwindcss.com"></script>';

function isLegacyThreePart(css: string, js: string): boolean {
  return Boolean((css || "").trim() || (js || "").trim());
}

function looksLikeFullHtmlDocument(text: string): boolean {
  const head = text.trim().slice(0, 200).toLowerCase();
  return head.startsWith("<!doctype") || head.startsWith("<html");
}

function ensureTailwindCdn(doc: string): string {
  if (doc.includes("cdn.tailwindcss.com")) return doc;
  if (doc.includes("</head>")) {
    return doc.replace("</head>", `  ${TAILWIND_CDN}\n</head>`);
  }
  return `${TAILWIND_CDN}\n${doc}`;
}

function wrapFragmentAsSingleFile(body: string): string {
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">${TAILWIND_CDN}</head><body class="min-h-screen bg-slate-950 text-slate-100 antialiased">${body}</body></html>`;
}

export function compileLocalTemplatePreview(
  html: string,
  css: string,
  js: string,
  options?: CompilePreviewOptions,
): string {
  const useSampleData = options?.useSampleData !== false;
  const rawHtml = (html || "").trim();
  if (!isLegacyThreePart(css, js)) {
    let doc = rawHtml;
    if (!doc) {
      doc = wrapFragmentAsSingleFile(
        '<p class="p-6 text-slate-400">Empty template — chat with the agent to design.</p>',
      );
    } else {
      doc = compileBindingsInTemplate(doc, useSampleData);
      if (!looksLikeFullHtmlDocument(doc)) {
        doc = wrapFragmentAsSingleFile(doc);
      } else {
        doc = ensureTailwindCdn(doc);
      }
    }
    const chromeBlock = options?.thumbnail
      ? `<style data-studio-thumbnail-chrome>${THUMBNAIL_PREVIEW_SHELL_CSS}</style>`
      : "";
    if (chromeBlock && doc.includes("</head>")) {
      doc = doc.replace("</head>", `${chromeBlock}</head>`);
    }
    if (!options?.thumbnail) {
      doc = appendLivePreviewChrome(doc);
    }
    return appendProposalBindingRuntime(doc);
  }

  let body = rawHtml;
  if (!body) {
    body =
      '<div style="padding:1.25rem;color:#64748b;font-family:system-ui,sans-serif;font-size:14px;">Empty template — chat with the agent to design.</div>';
  } else {
    body = compileBindingsInTemplate(body, useSampleData);
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
  return appendProposalBindingRuntime(doc);
}
