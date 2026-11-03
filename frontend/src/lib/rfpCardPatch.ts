/** Build partial card payload for validate_card_mutation from side-card form state. */
export type RfpCardFormState = {
  checkIn: string;
  checkOut: string;
  headcount: string;
  peakRooms: string;
  totalRoomNights: string;
  seatingStyle: string;
  cateringNotes: string;
  avSpecs: string;
};

export function cardsToFormState(cards: Record<string, unknown>): RfpCardFormState {
  const overview = (cards.event_overview as Record<string, unknown>) || {};
  const meeting = (cards.meeting_space as Record<string, unknown>) || {};
  const room = (cards.room_block as Record<string, unknown>) || {};
  const cateringAv = (cards.catering_av as Record<string, unknown>) || {};
  return {
    checkIn: String(overview.check_in_date || ""),
    checkOut: String(overview.check_out_date || ""),
    headcount: meeting.headcount != null ? String(meeting.headcount) : "",
    peakRooms: room.peak_rooms != null ? String(room.peak_rooms) : "",
    totalRoomNights: room.total_room_nights != null ? String(room.total_room_nights) : "",
    seatingStyle: String(meeting.seating_style || "classroom"),
    cateringNotes: String(cateringAv.catering ?? ""),
    avSpecs: String(cateringAv.av ?? ""),
  };
}

export function formStateToPatch(
  prev: RfpCardFormState,
  next: RfpCardFormState,
): Record<string, unknown> | null {
  const patch: Record<string, unknown> = {};
  const overview: Record<string, unknown> = {};
  if (next.checkIn !== prev.checkIn && next.checkIn) overview.check_in_date = next.checkIn;
  if (next.checkOut !== prev.checkOut && next.checkOut) overview.check_out_date = next.checkOut;
  if (Object.keys(overview).length) patch.event_overview = overview;

  const meeting: Record<string, unknown> = {};
  if (next.headcount !== prev.headcount && next.headcount !== "") {
    const n = Number(next.headcount);
    if (!Number.isNaN(n) && n >= 0) meeting.headcount = n;
  }
  if (next.seatingStyle !== prev.seatingStyle) meeting.seating_style = next.seatingStyle;
  if (Object.keys(meeting).length) patch.meeting_space = meeting;

  const room: Record<string, unknown> = {};
  if (next.peakRooms !== prev.peakRooms && next.peakRooms !== "") {
    const n = Number(next.peakRooms);
    if (!Number.isNaN(n) && n >= 0) room.peak_rooms = n;
  }
  if (next.totalRoomNights !== prev.totalRoomNights && next.totalRoomNights !== "") {
    const n = Number(next.totalRoomNights);
    if (!Number.isNaN(n) && n >= 0) room.total_room_nights = n;
  }
  if (Object.keys(room).length) patch.room_block = room;

  const cateringAv: Record<string, unknown> = {};
  if (next.cateringNotes !== prev.cateringNotes) {
    cateringAv.catering = next.cateringNotes;
  }
  if (next.avSpecs !== prev.avSpecs) {
    cateringAv.av = next.avSpecs;
  }
  if (Object.keys(cateringAv).length) patch.catering_av = cateringAv;

  return Object.keys(patch).length ? patch : null;
}

export function amberSet(cards: Record<string, unknown>, section: string): Set<string> {
  const block = (cards[section] as Record<string, unknown>) || {};
  const raw = block.amber_fields;
  if (!Array.isArray(raw)) return new Set();
  return new Set(raw.map(String));
}
