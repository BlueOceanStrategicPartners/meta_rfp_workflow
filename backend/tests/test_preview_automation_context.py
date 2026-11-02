from apps.designer_studio.preview_automation_context import validate_automation_request


def test_automation_depth_blocks_loops():
    err = validate_automation_request(
        preview_automation_depth=2,
        preview_automation_report={"ok": True},
        message="fix preview",
    )
    assert err is not None
