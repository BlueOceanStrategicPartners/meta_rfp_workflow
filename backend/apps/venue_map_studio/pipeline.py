from __future__ import annotations

from apps.core.exceptions import MapVectorizationFallbackHandler
from apps.inventory.models import InteractiveVenueMap, VenueMapZone


CONFIDENCE_THRESHOLD = 0.85


def stub_sam_segment(image_path: str) -> tuple[list[dict], float]:
    """Stub SAM: returns a single low-confidence polygon to trigger editor fallback."""
    return (
        [
            {
                "svg_element_id": "zone-1",
                "polygon": [[10, 10], [200, 10], [200, 120], [10, 120]],
                "label": "Unverified Hall",
            }
        ],
        0.6,
    )


def vectorize_map(venue_map: InteractiveVenueMap) -> InteractiveVenueMap:
    polygons, confidence = stub_sam_segment(venue_map.source_image_file.name)
    venue_map.vectorization_confidence = confidence
    if confidence < CONFIDENCE_THRESHOLD:
        venue_map.generated_html_svg = _editor_fallback_svg(polygons)
        venue_map.save(update_fields=["generated_html_svg", "vectorization_confidence"])
        raise MapVectorizationFallbackHandler(
            "Confidence below threshold; polygon editor enabled."
        )
    svg = _build_svg(polygons)
    venue_map.generated_html_svg = svg
    venue_map.save(update_fields=["generated_html_svg", "vectorization_confidence"])
    for poly in polygons:
        VenueMapZone.objects.update_or_create(
            venue_map=venue_map,
            svg_element_id=poly["svg_element_id"],
            defaults={
                "zone_label": poly.get("label", poly["svg_element_id"]),
                "polygon_coords_json": poly["polygon"],
            },
        )
    return venue_map


def _build_svg(polygons: list[dict]) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">',
    ]
    for poly in polygons:
        points = " ".join(f"{x},{y}" for x, y in poly["polygon"])
        parts.append(
            f'<polygon id="{poly["svg_element_id"]}" points="{points}" fill="rgba(0,180,255,0.2)" stroke="#0af"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _editor_fallback_svg(polygons: list[dict]) -> str:
    return _build_svg(polygons) + "<!-- polygon-editor-fallback -->"
