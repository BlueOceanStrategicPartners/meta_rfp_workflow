import pytest

from apps.rfp_debate.arbiter_orchestrator import ArbiterOrchestrator
from apps.rfp_debate.models import RFPSubmission


@pytest.mark.django_db
def test_debate_reaches_consensus(client_user):
    rfp = RFPSubmission.objects.create(
        client=client_user,
        source_document_text="MISMATCH_FIXTURE",
    )
    orchestrator = ArbiterOrchestrator()
    orchestrator.run_debate(rfp)
    rfp.refresh_from_db()
    assert rfp.status == "AWAITING_USER_CARD_EDIT"
    assert rfp.debate_logs.count() >= 1
    last = rfp.debate_logs.order_by("-iteration_number").first()
    assert last.arbiter_consensus_score >= 1.0 or last.discrepancy_flags_json == []
