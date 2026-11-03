/** Point-and-select elements in the Live preview iframe for scoped agent prompts. */

export type PreviewElementTarget = {
  tag: string;
  id: string;
  sectionId: string;
  sectionLabel: string;
  classSummary: string;
  selectorHint: string;
  textSnippet: string;
};

export type PickHighlightBox = {
  top: number;
  left: number;
  width: number;
  height: number;
};

const SKIP_TAGS = new Set(["HTML", "BODY", "HEAD", "SCRIPT", "STYLE", "META", "LINK", "TITLE"]);

const HIGHLIGHT_ROOT_SELECTOR =
  "section, article, header, footer, .venue-map-proposal, .proposal-cta, main, [class*='rounded-2xl'], [class*='rounded-xl']";

export function pickHighlightRoot(el: Element | null): Element | null {
  if (!el) return null;
  let node: Element | null = el;
  while (node && SKIP_TAGS.has(node.tagName)) {
    node = node.parentElement;
  }
  if (!node) return null;
  const root = node.closest(HIGHLIGHT_ROOT_SELECTOR);
  return root || node;
}

function classSummary(el: Element): string {
  const raw = (el.getAttribute("class") || "").trim();
  if (!raw) return "";
  const parts = raw.split(/\s+/).filter(Boolean);
  const meaningful = parts.filter(
    (c) =>
      !c.startsWith("hover:") &&
      !c.startsWith("focus:") &&
      !c.startsWith("md:") &&
      !c.startsWith("lg:") &&
      c.length < 48,
  );
  return meaningful.slice(0, 6).join(" ");
}

function textSnippet(el: Element): string {
  const text = (el.textContent || "").replace(/\s+/g, " ").trim();
  if (text.length <= 100) return text;
  return `${text.slice(0, 97)}…`;
}

function nearestSection(el: Element): { id: string; label: string } {
  const section = el.closest("section");
  if (!section) return { id: "", label: "" };
  const id = section.id || section.getAttribute("aria-label") || "";
  const heading = section.querySelector("h1,h2,h3,h4,h5");
  const label = (heading?.textContent || section.getAttribute("aria-label") || id || "").trim();
  return { id: id.trim(), label: label.slice(0, 120) };
}

function selectorHint(el: Element): string {
  const htmlEl = el as HTMLElement;
  if (htmlEl.id) return `#${cssEscape(htmlEl.id)}`;
  const { id: sectionId } = nearestSection(el);
  if (sectionId) return `section#${cssEscape(sectionId)}`;
  const cls = classSummary(el);
  if (cls) {
    const first = cls.split(/\s+/)[0];
    if (first) return `${el.tagName.toLowerCase()}.${first}`;
  }
  return el.tagName.toLowerCase();
}

function cssEscape(value: string): string {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(value);
  }
  return value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

export function describePreviewElement(el: Element): PreviewElementTarget | null {
  const root = pickHighlightRoot(el);
  if (!root || SKIP_TAGS.has(root.tagName)) return null;
  const { id: sectionId, label: sectionLabel } = nearestSection(root);
  const htmlEl = root as HTMLElement;
  return {
    tag: root.tagName.toLowerCase(),
    id: htmlEl.id || "",
    sectionId,
    sectionLabel,
    classSummary: classSummary(root),
    selectorHint: selectorHint(root),
    textSnippet: textSnippet(root),
  };
}

export function findElementForPreviewTarget(
  doc: Document,
  target: PreviewElementTarget,
): Element | null {
  if (target.id) {
    const byId = doc.getElementById(target.id);
    if (byId) return pickHighlightRoot(byId);
  }
  if (target.sectionId) {
    const section = doc.getElementById(target.sectionId);
    if (section) return pickHighlightRoot(section);
  }
  const hint = target.selectorHint.trim();
  if (hint.startsWith("#")) {
    try {
      const el = doc.querySelector(hint);
      if (el) return pickHighlightRoot(el);
    } catch {
      /* invalid selector */
    }
  }
  if (hint.startsWith("section#")) {
    const id = hint.slice("section#".length);
    const section = doc.getElementById(id);
    if (section) return pickHighlightRoot(section);
  }
  return null;
}

export function elementUnderPreviewPointer(
  iframe: HTMLIFrameElement,
  clientX: number,
  clientY: number,
): Element | null {
  const doc = iframe.contentDocument;
  if (!doc) return null;
  const rect = iframe.getBoundingClientRect();
  if (
    clientX < rect.left ||
    clientX > rect.right ||
    clientY < rect.top ||
    clientY > rect.bottom
  ) {
    return null;
  }
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  const raw = doc.elementFromPoint(x, y);
  return pickHighlightRoot(raw);
}

export function measurePickHighlightBox(
  scrollEl: HTMLElement,
  targetEl: Element,
): PickHighlightBox | null {
  const elRect = targetEl.getBoundingClientRect();
  const scrollRect = scrollEl.getBoundingClientRect();
  const top = elRect.top - scrollRect.top + scrollEl.scrollTop;
  const left = elRect.left - scrollRect.left + scrollEl.scrollLeft;
  const width = elRect.width;
  const height = elRect.height;
  if (width < 4 || height < 4) return null;
  const viewTop = scrollEl.scrollTop;
  const viewBottom = viewTop + scrollEl.clientHeight;
  const elBottom = top + height;
  if (elBottom < viewTop - 8 || top > viewBottom + 8) return null;
  return { top, left, width, height };
}

export const PREVIEW_TARGET_MESSAGE_PREFIX = "[Live preview target";

export function formatPreviewTargetForAgent(target: PreviewElementTarget): string {
  const lines = [
    "[Live preview target — scope your edit to THIS region in html_markup]",
    `- Section: ${target.sectionLabel || "—"}${target.sectionId ? ` (#${target.sectionId})` : ""}`,
    `- Element: <${target.tag}${target.id ? ` id="${target.id}"` : ""}>`,
  ];
  if (target.classSummary) lines.push(`- Classes: ${target.classSummary}`);
  if (target.textSnippet) lines.push(`- Visible text: ${target.textSnippet.slice(0, 160)}`);
  lines.push(`- Find in template: ${target.selectorHint}`);
  lines.push("Do not redesign unrelated sections unless the user asks.");
  return lines.join("\n");
}

export function composeMessageWithPreviewTarget(
  userText: string,
  target: PreviewElementTarget | null,
): string {
  const text = userText.trim();
  if (!target) return text;
  const block = formatPreviewTargetForAgent(target);
  if (!text) return block;
  return `${block}\n\n${text}`;
}

export type PreviewPickerSession = {
  onHover: (box: PickHighlightBox | null) => void;
  onSelect: (target: PreviewElementTarget) => void;
};

/** Bind pointer picking on a transparent shield over the iframe (iframe steals parent events). */
export function attachPreviewElementPickerSession(
  opts: {
    iframe: HTMLIFrameElement;
    scrollEl: HTMLElement;
    pointerEl: HTMLElement;
    handlers: PreviewPickerSession;
  },
): () => void {
  const { iframe, scrollEl, pointerEl, handlers } = opts;
  let hoverEl: Element | null = null;

  const syncHoverBox = (el: Element | null) => {
    if (!el) {
      handlers.onHover(null);
      return;
    }
    const box = measurePickHighlightBox(scrollEl, el);
    handlers.onHover(box);
  };

  const onMove = (event: MouseEvent) => {
    const el = elementUnderPreviewPointer(iframe, event.clientX, event.clientY);
    if (el === hoverEl) return;
    hoverEl = el;
    syncHoverBox(el);
  };

  const onClick = (event: MouseEvent) => {
    const el = elementUnderPreviewPointer(iframe, event.clientX, event.clientY);
    if (!el) return;
    event.preventDefault();
    event.stopPropagation();
    const described = describePreviewElement(el);
    if (!described) return;
    hoverEl = el;
    syncHoverBox(el);
    handlers.onSelect(described);
  };

  const onScroll = () => {
    if (hoverEl) syncHoverBox(hoverEl);
  };

  pointerEl.addEventListener("mousemove", onMove, true);
  pointerEl.addEventListener("click", onClick, true);
  scrollEl.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);

  return () => {
    pointerEl.removeEventListener("mousemove", onMove, true);
    pointerEl.removeEventListener("click", onClick, true);
    scrollEl.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", onScroll);
    handlers.onHover(null);
  };
}

export function measureLockedTargetBox(
  iframe: HTMLIFrameElement | null,
  scrollEl: HTMLElement | null,
  target: PreviewElementTarget | null,
): PickHighlightBox | null {
  if (!iframe || !scrollEl || !target) return null;
  const doc = iframe.contentDocument;
  if (!doc) return null;
  const el = findElementForPreviewTarget(doc, target);
  if (!el) return null;
  return measurePickHighlightBox(scrollEl, el);
}
