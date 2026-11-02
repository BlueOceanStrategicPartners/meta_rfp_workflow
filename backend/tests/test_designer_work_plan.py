from apps.designer_studio.designer_work_plan import (
    WorkPlanTracker,
    build_work_plan,
    guess_include_venue_map,
)


def test_build_work_plan_includes_optional_stages():
    steps = build_work_plan(
        message="Fix preview overlap on the map popup",
        include_preview_audit=True,
    )
    ids = [s["id"] for s in steps]
    assert "understand_brief" in ids
    assert "preview_audit" in ids
    assert "venue_map" not in ids
    assert ids[-1] == "finalize"


def test_work_plan_tracker_marks_active_and_done():
    tracker = WorkPlanTracker(
        [
            {"id": "a", "label": "A", "status": "pending"},
            {"id": "b", "label": "B", "status": "pending"},
        ]
    )
    tracker.set_status("a", "active")
    snap = tracker.set_status("a", "done")
    assert snap[0]["status"] == "done"
    tracker.set_status("b", "active")
    assert tracker.snapshot()[1]["status"] == "active"


def test_guess_include_venue_map_with_attachment():
    assert guess_include_venue_map("upload floorplan for the map", True) is True
