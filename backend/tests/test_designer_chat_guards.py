import pytest

from apps.designer_studio.designer_chat_guards import try_floorplan_attachment_reminder


@pytest.mark.django_db
def test_floorplan_upload_without_attachment_returns_reminder(designer_user):
    out = try_floorplan_attachment_reminder(
        message="Upload floorplan image",
        assets=[],
    )
    assert out is not None
    assert "don't see a floorplan attached" in out["assistant_message"].lower()
    assert out.get("attachment_required") is True


@pytest.mark.django_db
def test_proposal_design_not_treated_as_upload_only(designer_user):
    out = try_floorplan_attachment_reminder(
        message="Create interactive proposal with animations and hero",
        assets=[],
    )
    assert out is None
