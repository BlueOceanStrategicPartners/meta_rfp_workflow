const PLACEHOLDER_ORGS = new Set(["your organization", "your organisation", "voice rfp session"]);

/** Conversational questions should go to the voice assistant, not the 3-agent debate pipeline. */
export function messageLooksLikeClientQuestion(message: string): boolean {
  const t = message.trim();
  const lower = t.toLowerCase();
  if (t.includes("?")) return true;
  if (
    /\b(what kind of|what type of|what rooms?|how about your rooms?|tell me about your rooms)\b/i.test(
      lower,
    )
  ) {
    return true;
  }
  if (/\b(do you have|can you|could you|how many rooms|what do you offer)\b/i.test(lower) && t.length >= 40) {
    return true;
  }
  return false;
}

/** Small talk — no session, cards, or debate. */
export function messageIsSocialGreeting(message: string): boolean {
  const t = message.trim();
  if (!t || t.length > 140) return false;
  const lower = t.toLowerCase();
  if (/\b(\d+\s*(participants?|guests|rooms?|nights?)|next week|check[\s-]?in|room block)\b/i.test(lower)) {
    return false;
  }
  if (/^(start|run|begin|analyze|process)\b/i.test(lower)) return false;
  if (/^(hi|hello|hey|good\s+(morning|afternoon|evening))[\s,!.?]*/i.test(lower)) return true;
  if (lower.includes("how are you") && (t.includes("?") || t.length < 90)) {
    if (!/\b(book|rfp|room block|participants?)\b/i.test(lower)) return true;
  }
  if (/^(thanks?|thank you)[\s,!.?]*/i.test(lower) && t.length < 80) return true;
  return false;
}

/** Concrete dates, counts, or explicit run commands — not vague "book a room". */
export function messageHasActionableRfpDetails(message: string): boolean {
  const t = message.trim();
  const lower = t.toLowerCase();
  if (messageIsSocialGreeting(t)) return false;
  if (/^(start|run|begin|analyze|process)\b/i.test(t)) return true;
  if (messageLooksLikeClientQuestion(t)) return false;
  if (t.length >= 120 && !/\bnext week\b/i.test(lower)) return true;
  if (
    /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(people|peoples|persons|guests|attendees|pax|participants?)\b/i.test(
      t,
    )
  ) {
    return true;
  }
  if (/\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b/i.test(t)) return true;
  if (/\b\d+\s*rooms?\b/i.test(t)) return true;
  if (/\bnext week\b/i.test(t)) return true;
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

/** Run 3-agent extraction/debate only for pasted RFPs or explicit analyze — not normal voice Q&A. */
export function shouldRunDebateExtraction(message: string): boolean {
  if (messageIsSocialGreeting(message)) return false;
  if (messageLooksLikeClientQuestion(message)) return false;
  if (detectPlanningTurn(message)) return false;
  const t = message.trim();
  const lower = t.toLowerCase();
  if (/^(start|run|begin|analyze|process)\b/i.test(lower)) return true;
  if (t.length >= 200 && /\b(rfp|proposal|catering|breakout|room block)\b/i.test(lower)) return true;
  if (/\b(attach|upload|pdf)\b/i.test(lower)) return true;
  return false;
}

function detectPlanningTurn(message: string): boolean {
  const lower = message.toLowerCase();
  if (/\bnext week\b/.test(lower)) return true;
  if (/\bwhat kind of rooms?\b|\bhow about your rooms?\b/.test(lower)) return true;
  if (/\b(\d+)\s*participants?\b/.test(lower)) return true;
  if (/\bseveral rooms?\b|\bmultiple rooms?\b/.test(lower)) return true;
  return false;
}

/** @deprecated Use shouldRunDebateExtraction */
export function shouldStartAutonomousPipeline(message: string): boolean {
  return shouldRunDebateExtraction(message);
}

/** Create an RFP row when we need to persist card patches or run extraction. */
export function shouldEnsureRfpSession(message: string): boolean {
  if (messageIsSocialGreeting(message)) return false;
  return messageHasActionableRfpDetails(message) || shouldRunDebateExtraction(message);
}

/** Cards visible only after real fields — not placeholder org shell. */
export function cardsHaveIdentifiedFields(cards: Record<string, unknown>): boolean {
  if (!cards || !Object.keys(cards).length) return false;
  const overview = (cards.event_overview as Record<string, unknown>) || {};
  const room = (cards.room_block as Record<string, unknown>) || {};
  const meeting = (cards.meeting_space as Record<string, unknown>) || {};
  const quote = (cards.live_quote as Record<string, unknown>) || {};

  const org = String(overview.company_name || "")
    .trim()
    .toLowerCase();
  if (org && !PLACEHOLDER_ORGS.has(org)) return true;

  for (const key of ["check_in_date", "check_out_date"] as const) {
    const val = String(overview[key] || "").trim();
    if (val && val.toUpperCase() !== "TBD") return true;
  }
  if (room.total_room_nights || room.peak_rooms) return true;
  const headcount = Number(meeting.headcount);
  if (headcount > 0) return true;
  if (quote.anchor_price != null && quote.anchor_price !== "") return true;
  return false;
}

/** Room-only stay — hide meeting / catering cards and proposal meeting bindings. */
export function sessionNeedsMeetingSpace(
  clientSession?: { intake?: Record<string, string> },
  cards?: Record<string, unknown>,
): boolean {
  const flag = String(clientSession?.intake?.needs_meeting_space ?? "").toLowerCase();
  if (flag === "0" || flag === "false" || flag === "no") return false;
  const meeting = (cards?.meeting_space as Record<string, unknown>) || {};
  if (meeting.included === false) return false;
  return true;
}

/** Back-compat alias */
export function cardsHaveExtraction(cards: Record<string, unknown>): boolean {
  return cardsHaveIdentifiedFields(cards);
}

/** Immediate spoken-style ack while the backend pipeline runs. */
export function quickVoiceAck(message: string): string {
  if (messageIsSocialGreeting(message)) return "";
  const lower = message.toLowerCase();
  const bits: string[] = [];
  const people = lower.match(
    /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(people|peoples|persons|guests|attendees|pax|participants?)\b/,
  );
  if (people) bits.push(`${people[1]} guests`);
  const nights = lower.match(/\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?\b/);
  if (nights) bits.push(`${nights[1]} nights`);
  if (/\bnext week\b/.test(lower)) bits.push("next week");
  if (/\b(next month|january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}(st|nd|rd|th)?)\b/.test(lower)) {
    bits.push("those dates");
  }
  if (bits.length) {
    return `Got it — ${bits.join(", ")}. One moment…`;
  }
  return "";
}
