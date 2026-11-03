import type { ChatMessage, ChatPreviewTargetAttachment } from "./designerApi";
import {
  PREVIEW_TARGET_MESSAGE_PREFIX,
  type PreviewElementTarget,
} from "./designerPreviewElementPicker";

/** Split stored user message into card attachment + visible text (legacy plain-block support). */
export function userMessageDisplayParts(msg: ChatMessage): {
  text: string;
  previewTarget: ChatPreviewTargetAttachment | null;
} {
  const structured = normalizePreviewTargetAttachment(msg.preview_target);
  if (structured) {
    return { text: (msg.content || "").trim(), previewTarget: structured };
  }
  const content = msg.content || "";
  if (!content.includes(PREVIEW_TARGET_MESSAGE_PREFIX)) {
    return { text: content, previewTarget: null };
  }
  const split = content.indexOf("\n\n");
  const block = split >= 0 ? content.slice(0, split) : content;
  const text = split >= 0 ? content.slice(split + 2).trim() : "";
  return { text, previewTarget: parsePreviewTargetBlock(block) };
}

export function normalizePreviewTargetAttachment(
  raw: unknown,
): ChatPreviewTargetAttachment | null {
  if (!raw || typeof raw !== "object") return null;
  const rec = raw as Record<string, unknown>;
  const tag = String(rec.tag || "section");
  return {
    tag,
    id: String(rec.id || ""),
    sectionId: String(rec.sectionId || rec.section_id || ""),
    sectionLabel: String(rec.sectionLabel || rec.section_label || ""),
    classSummary: String(rec.classSummary || rec.class_summary || ""),
    selectorHint: String(rec.selectorHint || rec.selector_hint || ""),
    textSnippet: String(rec.textSnippet || rec.text_snippet || ""),
  };
}

function parsePreviewTargetBlock(block: string): ChatPreviewTargetAttachment | null {
  const sectionMatch = block.match(/- Section:\s*(.+?)(?:\s+\(#([^)]+)\))?\s*$/m);
  const elementMatch = block.match(/- Element:\s*<(\w+)(?:\s+id="([^"]*)")?>/i);
  const classesMatch = block.match(/- Classes:\s*(.+)$/m);
  const snippetMatch = block.match(/- Visible text:\s*(.+)$/m);
  const selectorMatch = block.match(/- Find in template:\s*(.+)$/m);
  if (!sectionMatch && !elementMatch && !selectorMatch) return null;
  return {
    tag: elementMatch?.[1]?.toLowerCase() || "section",
    id: elementMatch?.[2] || "",
    sectionId: sectionMatch?.[2] || "",
    sectionLabel: (sectionMatch?.[1] || "").replace(/\s*\([^)]*\)\s*$/, "").trim(),
    classSummary: classesMatch?.[1]?.trim() || "",
    textSnippet: snippetMatch?.[1]?.trim() || "",
    selectorHint: selectorMatch?.[1]?.trim() || "",
  };
}

export function previewTargetToAttachment(
  target: PreviewElementTarget,
): ChatPreviewTargetAttachment {
  return { ...target };
}
