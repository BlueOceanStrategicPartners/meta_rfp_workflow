/** Concrete dates, counts, or explicit run commands — not vague "book a room". */
export function messageHasActionableRfpDetails(message: string): boolean {
  const t = message.trim();
  const lower = t.toLowerCase();
  if (/^(start|run|begin|analyze|process)\b/i.test(t)) return true;
  if (t.length >= 120) return true;
  if (
    /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(people|peoples|persons|guests|attendees|pax)\b/i.test(
      t,
    )
  ) {
    return true;
  }
  if (/\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b/i.test(t)) return true;
  if (/\b\d+\s*rooms?\b/i.test(t)) return true;
  if (
    /\b(january|february|march|april|may|june|july|august|september|october|november|december|next month)\b/i.test(
      t,
    )
  ) {
    return true;
  }
    if (
    /\b(arriv|depart|check[\s-]?in|check[\s-]?out)\b/i.test(t) &&
    /\b(\d{1,2}(st|nd|rd|th)?|\d+\s*rooms?\b)/i.test(t)
  ) {
    return true;
  }
  if (/\b\d{1,2}(st|nd|rd|th)\b/.test(lower) && /\b\d{1,2}(st|nd|rd|th)\b/.test(t.slice(t.search(/\d{1,2}(st|nd|rd|th)/) + 1))) {
    return true;
  }
  if (/\b(headcount|ballroom|catering|room block|block of)\b/i.test(t) && t.length >= 40) return true;
  return false;
}

/** When to run 3-agent debate + pricing (not on casual chat like "hi" or "book a room"). */
export function shouldStartAutonomousPipeline(message: string): boolean {
  if (!messageHasActionableRfpDetails(message)) return false;
  const t = message.trim();
  return /\b(room|rooms|night|nights|stay|event|meeting|rfp|summit|conference|block|catering|ballroom)\b/i.test(
    t,
  );
}

/** Immediate spoken-style ack while the backend pipeline runs. */
export function quickVoiceAck(message: string): string {
  const lower = message.toLowerCase();
  const bits: string[] = [];
  const people = lower.match(
    /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(people|peoples|persons|guests|attendees|pax)\b/,
  );
  if (people) bits.push(`${people[1]} guests`);
  const nights = lower.match(/\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b/);
  if (nights) bits.push(`${nights[1]} nights`);
  if (/\b(next month|january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}(st|nd|rd|th)?)\b/.test(lower)) {
    bits.push("those dates");
  }
  if (bits.length) {
    return `Got it — ${bits.join(", ")}. I'm building your summary now.`;
  }
  return "Happy to help — tell me your dates, nights, and group size when you're ready.";
}

export function cardsHaveExtraction(cards: Record<string, unknown>): boolean {
  const overview = (cards.event_overview as Record<string, unknown>) || {};
  if (overview.company_name) return true;
  const room = (cards.room_block as Record<string, unknown>) || {};
  const meeting = (cards.meeting_space as Record<string, unknown>) || {};
  return Boolean(room.total_room_nights || meeting.headcount || overview.check_in_date);
}
