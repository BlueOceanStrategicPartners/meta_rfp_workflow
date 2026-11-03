import pytest

from apps.rfp_debate.models import RFPStatus


@pytest.mark.django_db
def test_telemetry_shape_funnel_and_conversion(admin_client, seeded_rfp):
    body = admin_client.get("/api/admin-center/telemetry/").json()
    assert [row["status"] for row in body["funnel"]] == list(RFPStatus.values)
    assert body["conversion"] == {"booked": 0, "total": 1, "rate": 0.0}
    assert body["sla"]["recent"][0]["rfp_id"] == str(seeded_rfp.id)
    assert body["sla"]["p50_seconds"] is not None
    assert body["debate"]["avg_rounds"] >= 1
    assert body["pricing"]["fallback_rate"] == 1.0
    assert body["tokens"] is None


@pytest.mark.django_db
def test_sla_completed_at_written_once(seeded_rfp):
    from apps.dynamic_pricing.services import compute_dynamic_quote
    from apps.rfp_debate.tasks import _apply_quote_to_cards

    first = seeded_rfp.sla_completed_at
    assert first is not None
    # A later reprice must not move the SLA finish time.
    _apply_quote_to_cards(seeded_rfp, compute_dynamic_quote(seeded_rfp))
    seeded_rfp.refresh_from_db()
    assert seeded_rfp.sla_completed_at == first


@pytest.mark.django_db
def test_booked_counts_as_conversion(admin_client, seeded_rfp):
    seeded_rfp.status = RFPStatus.BOOKED
    seeded_rfp.save(update_fields=["status"])
    body = admin_client.get("/api/admin-center/telemetry/").json()
    assert body["conversion"]["rate"] == 1.0
