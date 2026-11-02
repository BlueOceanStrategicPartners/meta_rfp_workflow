from apps.designer_studio.designer_map_orchestration import (
    should_run_map_stage,
    user_wants_direct_create,
)


def test_user_wants_direct_create():
    assert user_wants_direct_create("Just create the proposal, skip questions")
    assert not user_wants_direct_create("Luxury theme please")


def test_should_run_map_with_skip_and_slot():
    design = {
        "html_markup": "<div>{{selected_map_svg}}</div>",
        "assistant_message": "Added map slot.",
        "clarification_options": [],
    }
    assert should_run_map_stage(
        message="Build proposal and map — skip questions",
        design_result=design,
        has_image_attachment=False,
        skip_questions=True,
    )


def test_should_not_run_map_when_only_asking():
    design = {
        "html_markup": "<div>{{selected_map_svg}}</div>",
        "assistant_message": "Please upload a floorplan?",
        "clarification_options": ["I'll upload a floorplan image"],
    }
    assert not should_run_map_stage(
        message="Create proposal with map",
        design_result=design,
        has_image_attachment=False,
        skip_questions=False,
    )
