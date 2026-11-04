"""Numbers for the Overview dashboard and the Telemetry page."""
from __future__ import annotations

import math

from django.db.models import Avg, Count, Max, Min

from apps.admin_command_center import audit
from apps.admin_command_center.models import AdminAuditEvent
from apps.dynamic_pricing.models import DynamicPricingQuote
from apps.dynamic_pricing import services as pricing_services
from apps.inventory.models import HistoricalOccupancy, SpaceInventory, VenueProperty
from apps.rfp_debate.models import DebateIterationLog, RFPStatus, RFPSubmission

from .rfps import attention_items, company_name

SLA_TARGET_SECONDS = 120


def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile; None when there is no data."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return round(ordered[rank - 1], 2)


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def sla_stats(*, recent_limit: int = 0) -> dict:
    rows = RFPSubmission.objects.exclude(sla_started_at__isnull=True).exclude(
        sla_completed_at__isnull=True
    ).order_by("-sla_started_at")
    durations = []
    recent = []
    for rfp in rows:
        seconds = (rfp.sla_completed_at - rfp.sla_started_at).total_seconds()
        if seconds < 0:
            continue  # clock skew; keep it out of the percentiles
        durations.append(seconds)
        if len(recent) < recent_limit:
            recent.append(
                {
                    "rfp_id": str(rfp.id),
                    "company_name": company_name(rfp),
                    "status": rfp.status,
                    "duration_seconds": round(seconds, 2),
                    "started_at": rfp.sla_started_at.isoformat(),
                }
            )
    within = sum(1 for d in durations if d <= SLA_TARGET_SECONDS)
    data = {
        "target_seconds": SLA_TARGET_SECONDS,
        "measured": len(durations),
        "p50_seconds": percentile(durations, 50),
        "p95_seconds": percentile(durations, 95),
        "within_target_pct": _ratio(within, len(durations)),
    }
    if recent_limit:
        data["recent"] = recent
    return data


def status_counts() -> dict[str, int]:
    counts = {s.value: 0 for s in RFPStatus}
    for row in RFPSubmission.objects.values("status").annotate(n=Count("id")):
        counts[row["status"]] = row["n"]
    return counts


def debate_stats() -> dict:
    logs = DebateIterationLog.objects.all()
    total_rounds = logs.count()
    rfp_ids = list(logs.values_list("rfp_id", flat=True).distinct())
    final_scores = []
    for row in logs.values("rfp_id").annotate(last=Max("iteration_number")):
        log = logs.filter(rfp_id=row["rfp_id"], iteration_number=row["last"]).first()
        if log:
            final_scores.append(log.arbiter_consensus_score)
    partial = RFPSubmission.objects.filter(pk__in=rfp_ids).exclude(amber_conflict_fields_json=[]).count()
    avg_ms = logs.aggregate(v=Avg("duration_ms"))["v"]
    return {
        "rounds": total_rounds,
        "avg_rounds": round(total_rounds / len(rfp_ids), 2) if rfp_ids else None,
        "avg_consensus": round(sum(final_scores) / len(final_scores), 4) if final_scores else None,
        "partial_rate": _ratio(partial, len(rfp_ids)),
        "avg_critic_ms": round(avg_ms) if avg_ms is not None else None,
    }


def pricing_stats() -> dict:
    total = DynamicPricingQuote.objects.count()
    fallback = DynamicPricingQuote.objects.filter(used_fallback_engine=True).count()
    return {
        "quotes": total,
        "fallback_rate": _ratio(fallback, total),
        "model_trained": pricing_services.model_status()["is_active"],
    }


def occupancy_range() -> dict:
    agg = HistoricalOccupancy.objects.aggregate(lo=Min("target_date"), hi=Max("target_date"))
    return {
        "rows": HistoricalOccupancy.objects.count(),
        "from": agg["lo"].isoformat() if agg["lo"] else None,
        "to": agg["hi"].isoformat() if agg["hi"] else None,
    }


def build_overview() -> dict:
    by_status = status_counts()
    debate = debate_stats()
    events = AdminAuditEvent.objects.select_related("actor")[:10]
    return {
        "rfps": {"total": sum(by_status.values()), "by_status": by_status},
        "sla": sla_stats(),
        "debate": {
            "rounds": debate["rounds"],
            "avg_consensus": debate["avg_consensus"],
            "partial_rate": debate["partial_rate"],
        },
        "pricing": pricing_stats(),
        "inventory": {
            "properties": VenueProperty.objects.count(),
            "spaces": SpaceInventory.objects.count(),
            "booked": SpaceInventory.objects.filter(is_booked=True).count(),
        },
        "occupancy": occupancy_range(),
        "attention": attention_items(),
        "recent_activity": [audit.serialize_event(e) for e in events],
    }


def build_telemetry() -> dict:
    by_status = status_counts()
    total = sum(by_status.values())
    booked = by_status.get(RFPStatus.BOOKED, 0)
    pricing = pricing_stats()
    debate = debate_stats()
    return {
        "sla": sla_stats(recent_limit=20),
        "funnel": [{"status": s.value, "count": by_status[s.value]} for s in RFPStatus],
        "conversion": {"booked": booked, "total": total, "rate": _ratio(booked, total)},
        "debate": {
            "avg_rounds": debate["avg_rounds"],
            "avg_consensus": debate["avg_consensus"],
            "partial_rate": debate["partial_rate"],
            "avg_critic_ms": debate["avg_critic_ms"],
        },
        "pricing": {"quotes": pricing["quotes"], "fallback_rate": pricing["fallback_rate"]},
        "tokens": None,
    }
