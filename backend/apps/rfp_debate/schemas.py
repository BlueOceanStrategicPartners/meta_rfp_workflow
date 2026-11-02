from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    page_number: int
    bounding_box: list[float] = Field(default_factory=list)
    verbatim_quote: str


class ExtractedField(BaseModel):
    value: Any
    source_citation: SourceCitation


class RoomBlockNight(BaseModel):
    date: str
    single: int = 0
    double: int = 0
    deluxe: int = 0
    suite: int = 0


class RoomBlockLineItem(BaseModel):
    """Proposal table row — maps to {{verified_room_blocks}} tbody columns."""

    category_name: str
    category_subtitle: str = ""
    badge: str = ""
    date_range: str = ""
    nights: int = 0
    quantity: int = 0
    rate_per_night: float | int | None = None
    estimated_total: float | int | None = None


class RoomBlockSummary(BaseModel):
    rooms_per_night: int = 0
    nights: int = 0
    room_nights: int = 0
    avg_rate_per_night: int = 0
    grand_total: int = 0
    policy_notes: str = ""


class RFPExtractionPayload(BaseModel):
    company_name: ExtractedField | None = None
    event_type: ExtractedField | None = None
    check_in_date: ExtractedField | None = None
    check_out_date: ExtractedField | None = None
    total_room_nights: ExtractedField | None = None
    room_blocks: list[RoomBlockNight] = Field(default_factory=list)
    meeting_headcount: ExtractedField | None = None
    seating_style: ExtractedField | None = None
    catering_notes: ExtractedField | None = None
    av_specs: ExtractedField | None = None
    historical_discount_pct: ExtractedField | None = None

    def consensus_score(self) -> float:
        fields = [
            self.company_name,
            self.event_type,
            self.check_in_date,
            self.check_out_date,
            self.total_room_nights,
            self.meeting_headcount,
        ]
        present = sum(1 for f in fields if f is not None)
        return present / max(len(fields), 1)


class DiscrepancyFlag(BaseModel):
    field_path: str
    severity: str
    message: str
    expected: str | None = None
    actual: str | None = None


class CritiqueResult(BaseModel):
    discrepancy_flags: list[DiscrepancyFlag] = Field(default_factory=list)
    consensus_score: float = 1.0

    @property
    def has_discrepancies(self) -> bool:
        return len(self.discrepancy_flags) > 0


class DiscrepancyReport(CritiqueResult):
    pass
