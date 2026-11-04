/** Plain-language cleanup for designer progress labels (non-technical users). */

const REPLACEMENTS: Array<[RegExp, string]> = [
  [/langgraph/gi, ""],
  [/\(langgraph\)/gi, ""],
  [/validator\s*\([^)]*\)/gi, "quality review"],
  [/calling design model[^.…]*/gi, "Working on your design"],
  [/turn \d+ of \d+/gi, ""],
  [/html,?\s*css,?\s*(and )?js/gi, "the proposal design"],
  [/\btemplate\b/gi, "proposal"],
  [/read template lines?/gi, "Review part of the proposal"],
  [/append to template/gi, "Add new content"],
  [/verify layout rules?/gi, "Run quality checks"],
  [/search template/gi, "Search the proposal"],
  [/planning agent/gi, "Planning"],
  [/executor agent/gi, "Muse Wonder"],
  [/design agent/gi, "Muse Wonder"],
];

export function normalizeDesignerProgressLabel(text: string): string {
  let out = (text || "").trim();
  if (!out) return out;
  for (const [pattern, repl] of REPLACEMENTS) {
    out = out.replace(pattern, repl);
  }
  out = out.replace(/\s{2,}/g, " ").replace(/\s+—\s+—/g, " — ").trim();
  return out || "Working on your design…";
}
