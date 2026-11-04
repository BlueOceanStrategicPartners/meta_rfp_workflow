/** Strip automation glitches and stray "undefined" prefixes from composer/voice text. */
export function sanitizeClientMessage(text: string): string {
  let cleaned = (text || "").trim();
  if (cleaned.toLowerCase().startsWith("undefined")) {
    cleaned = cleaned.slice("undefined".length).trim();
  }
  return cleaned;
}
