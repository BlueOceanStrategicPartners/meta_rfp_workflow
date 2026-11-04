"""3-agent debate with a real API key: re-checks keep good details, sample answers never leak in."""
import httpx
import pytest

from apps.core.exceptions import MaxDebateIterationsExceededError
from apps.rfp_debate.arbiter_orchestrator import ArbiterOrchestrator, merge_reextraction
from apps.rfp_debate.critic_agent import CriticAgent
from apps.rfp_debate.extractor_agent import ExtractorAgent
from apps.rfp_debate.meta_client import MetaModelAPIError, MetaModelClient, parse_extraction
from apps.rfp_debate.models import RFPSubmission

SOURCE = "Analyze this RFP: Acme Corp sales summit, check-in December 14 2026, check-out December 17 2026."


def field(value, quote="from the request"):
    return {"value": value, "source_citation": {"page_number": 1, "verbatim_quote": quote}}


DECEMBER = {
    "company_name": field("Acme Corp"),
    "event_type": field("Sales summit"),
    "check_in_date": field("2026-12-14", "check-in December 14 2026"),
    "check_out_date": field("2026-12-17", "check-out December 17 2026"),
    "total_room_nights": field(180),
    "meeting_headcount": field(200),
}


def flag(path):
    return {"discrepancy_flags": [{"field_path": path, "severity": "high", "message": "check"}], "consensus_score": 0.0}


AGREE = {"discrepancy_flags": [], "consensus_score": 1.0}


class ScriptedClient(MetaModelClient):
    """A live-mode client (real key) that replies from a script: dicts are answers, exceptions are failures."""

    def __init__(self, replies):
        super().__init__(api_key="test-key")
        self.replies = list(replies)
        self.calls = []

    @property
    def uses_fixtures(self):
        return False

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _debate(extractor_replies, critic_replies):
    extractor = ExtractorAgent(client=ScriptedClient(extractor_replies))
    critic = CriticAgent(client=ScriptedClient(critic_replies))
    return ArbiterOrchestrator(extractor=extractor, critic=critic), extractor


@pytest.fixture
def rfp(client_user):
    return RFPSubmission.objects.create(client=client_user, source_document_text=SOURCE)


@pytest.mark.django_db
def test_recheck_only_updates_the_flagged_field(rfp):
    arbiter, extractor = _debate([DECEMBER, {"total_room_nights": field(170)}], [flag("total_room_nights"), AGREE])
    arbiter.run_debate(rfp)
    rfp.refresh_from_db()
    overview = rfp.active_ui_cards_json["event_overview"]
    assert overview["check_in_date"] == "2026-12-14" and overview["company_name"] == "Acme Corp"  # kept
    assert rfp.active_ui_cards_json["room_block"]["total_room_nights"] == 170  # corrected
    assert rfp.status == "AWAITING_USER_CARD_EDIT" and rfp.debate_logs.count() == 2
    assert "MISMATCH_FIXTURE" not in extractor.client.calls[1]["user_content"]  # test hook stays out of real text
    assert extractor.client.calls[0]["allow_fixture_fallback"] is False


@pytest.mark.django_db
def test_failed_recheck_keeps_the_last_good_answer(rfp):
    broken = MetaModelAPIError("invalid structured output")
    arbiter, _ = _debate([DECEMBER, broken, broken], [flag("total_room_nights")])
    with pytest.raises(MaxDebateIterationsExceededError):
        arbiter.run_debate(rfp)
    rfp.refresh_from_db()
    assert rfp.active_ui_cards_json["event_overview"]["check_in_date"] == "2026-12-14"
    assert rfp.amber_conflict_fields_json == ["total_room_nights"]
    assert "Sample quote" not in str(rfp.verified_extraction_json) and "2026-06-01" not in str(rfp.verified_extraction_json)


@pytest.mark.django_db
def test_never_saves_an_answer_the_critic_did_not_check(rfp, monkeypatch):
    monkeypatch.setattr(ArbiterOrchestrator, "MAX_ITERATIONS", 2)
    arbiter, extractor = _debate(
        [DECEMBER, {"check_in_date": field("2026-12-15")}, {"check_in_date": field("2027-01-01")}],
        [flag("check_in_date"), flag("check_in_date")],
    )
    with pytest.raises(MaxDebateIterationsExceededError):
        arbiter.run_debate(rfp)
    rfp.refresh_from_db()
    assert len(extractor.client.calls) == 2  # no extra, unchecked re-check after the last round
    last_round = rfp.debate_logs.order_by("-iteration_number").first()
    assert rfp.verified_extraction_json == last_round.extractor_output_json
    assert rfp.active_ui_cards_json["event_overview"]["check_in_date"] == "2026-12-15"


def test_merge_rules():
    previous = parse_extraction(DECEMBER)
    fresh = parse_extraction({"total_room_nights": field(170), "check_in_date": field("2030-01-01"), "av_specs": field("PA")})
    merged = merge_reextraction(previous, fresh, ["total_room_nights"])
    assert merged.total_room_nights.value == 170  # flagged → updated
    assert merged.check_in_date.value == "2026-12-14"  # not flagged → kept even though the reply differs
    assert merged.av_specs.value == "PA"  # empty before → filled
    assert merge_reextraction(previous, fresh, ["meeting_headcount"]).total_room_nights.value == 180
    # linked fields: a nightly-block flag re-checks the total too, and a date flag re-checks both dates
    assert merge_reextraction(previous, fresh, ["room_blocks[0].single"]).total_room_nights.value == 170
    assert merge_reextraction(previous, fresh, ["check_out_date"]).check_in_date.value == "2030-01-01"


@pytest.mark.django_db
def test_real_key_with_a_broken_reply_never_uses_sample_answers(settings, monkeypatch):
    settings.USE_FIXTURE_DEBATE = False
    settings.META_MODEL_API_KEY = "test-key"

    def broken_post(self, url, **kwargs):
        return httpx.Response(200, json={"choices": [{"message": {"content": "Sorry, I can't help with that."}}]}, request=httpx.Request("POST", url))

    def no_samples(*args, **kwargs):
        raise AssertionError("sample answer used with a real API key")

    monkeypatch.setattr(httpx.Client, "post", broken_post)
    monkeypatch.setattr(MetaModelClient, "_fixture_response", no_samples)

    with pytest.raises(MetaModelAPIError):
        ExtractorAgent().extract(SOURCE)
    critique = CriticAgent().critique(SOURCE, parse_extraction(DECEMBER))  # falls back to deterministic checks
    assert critique.discrepancy_flags == [] and critique.consensus_score == 1.0


def test_live_critic_failure_keeps_the_room_maths_check():
    extraction = parse_extraction({**DECEMBER, "room_blocks": [{"date": "2026-12-14", "double": 50}]})
    critique = CriticAgent(client=ScriptedClient([MetaModelAPIError("down")])).critique(SOURCE, extraction)
    assert [f.field_path for f in critique.discrepancy_flags] == ["total_room_nights"]
    assert critique.consensus_score == 0.0
