from apps.venue_map_studio.map_component_contract import (
    build_reference_map_component,
    pick_floorplan_url,
)
from apps.venue_map_studio.map_services import deterministic_map_checks


def test_pick_floorplan_url_prefers_floorplan_name():
    block = (
        "Attached media assets:\n"
        "- lobby.jpg [IMAGE] url=https://cdn.example/lobby.jpg\n"
        "- floorplan.png [IMAGE] url=https://cdn.example/floorplan.png\n"
    )
    assert pick_floorplan_url(block) == "https://cdn.example/floorplan.png"


def test_reference_component_passes_deterministic_checks():
    ref = build_reference_map_component(floorplan_url="https://cdn.example/plan.png")
    issues = deterministic_map_checks(
        ref["html_markup"],
        ref["css_stylesheet"],
        ref["js_script"],
        ref["locations"],
    )
    assert issues == []
    assert "map-floorplan" in ref["html_markup"]
    assert "mouseenter" in ref["js_script"]
    assert "venue-map-root" in ref["html_markup"]
