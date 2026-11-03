from apps.negotiation_agent.voice_card_updates import parse_voice_card_patch


def test_peak_rooms_100_not_one():
    msg = (
        "If we allow to come Tuesday and if one participant needs one room, "
        "that means 100 need 100 rooms."
    )
    patch = parse_voice_card_patch(msg)
    assert patch is not None
    assert patch["room_block"]["peak_rooms"] == 100
    assert patch["meeting_space"]["headcount"] == 100
