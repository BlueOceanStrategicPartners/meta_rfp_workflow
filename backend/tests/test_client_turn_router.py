import pytest

from apps.negotiation_agent.client_turn_router import is_social_greeting, needs_debate_extraction
from apps.rfp_debate.card_identified import cards_have_identified_fields


def test_social_greeting():
    assert is_social_greeting("Hi, how are you doing? Thank you very much.")
    assert not is_social_greeting("We have 100 participants next week")


def test_debate_only_on_extraction():
    assert not needs_debate_extraction("Hi, how are you?")
    long_rfp = "Corporate room block and catering. " * 15 + "Full RFP breakout space."
    assert needs_debate_extraction(long_rfp)


def test_placeholder_org_not_identified():
    assert not cards_have_identified_fields(
        {
            "event_overview": {"company_name": "Your organization"},
            "room_block": {},
            "meeting_space": {},
        }
    )
    assert cards_have_identified_fields({"meeting_space": {"headcount": 20}})
