/** Map-only markup for library card previews (mirrors backend map_markup_guard). */
import { compileLocalMapPreview } from "./mapStudioPreview";

const PROPOSAL_MARKERS = [
  "{{client_name}}",
  "{{selected_map_svg}}",
  "venue-map-proposal",
  "proposal-venue-map",
  "proposal-cta",
];

const ROOT_OPEN =
  /<div[^>]*(?:\bvenue-map-root\b|\bid=["']venue-map["'])[^>]*>/i;

function sliceBalancedDiv(html: string, start: number): string {
  let depth = 0;
  let i = start;
  const n = html.length;
  while (i < n) {
    const tail = html.slice(i, i + 5).toLowerCase();
    if (tail.startsWith("<div")) {
      depth += 1;
      const close = html.indexOf(">", i);
      i = close >= 0 ? close + 1 : i + 1;
      continue;
    }
    if (tail.startsWith("</div")) {
      depth -= 1;
      const close = html.indexOf(">", i);
      i = close >= 0 ? close + 1 : i + 6;
      if (depth === 0) return html.slice(start, i);
      continue;
    }
    i += 1;
  }
  return html.slice(start);
}

export function extractInteractiveMapMarkup(html: string): string {
  const text = (html || "").trim();
  if (!text) return "";

  const match = text.match(ROOT_OPEN);
  if (match && match.index != null) {
    const fragment = sliceBalancedDiv(text, match.index).trim();
    if (fragment) return fragment;
  }

  const lower = text.toLowerCase();
  const looksProposal = PROPOSAL_MARKERS.some((m) => text.includes(m));
  if (looksProposal && !lower.includes("data-location-id")) return "";

  if (lower.includes("data-location-id") || lower.includes("map-popup")) return text;
  if (looksProposal) return "";
  return text;
}

const LIBRARY_PREVIEW_CSS = `
body[data-map-library-preview="1"] .map-popup,
body[data-map-library-preview="1"] #map-popup,
body[data-map-library-preview="1"] [role="dialog"] {
  display: none !important;
  visibility: hidden !important;
  opacity: 0 !important;
}
body[data-map-library-preview="1"] .venue-map-root,
body[data-map-library-preview="1"] #venue-map {
  min-height: 100%;
  width: 100%;
}
`;

/** Compile thumbnail preview: map fragment only, popups suppressed, no proposal chrome. */
export function compileMapLibraryCardPreview(html: string, css: string, js: string): string {
  const fragment = extractInteractiveMapMarkup(html);
  const body = fragment
    ? `<div data-map-library-preview="1">${fragment}</div>`
    : "";
  const mergedCss = `${css || ""}\n${LIBRARY_PREVIEW_CSS}`;
  const doc = compileLocalMapPreview(body, mergedCss, js || "");
  return doc.replace("<body>", '<body data-map-library-preview="1">');
}
