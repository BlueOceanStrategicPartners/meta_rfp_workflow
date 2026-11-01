from __future__ import annotations

from django.utils import timezone

from apps.inventory.models import InteractiveVenueMap


def append_map_revision(venue_map: InteractiveVenueMap, *, note: str = "save") -> None:
    history = list(venue_map.revision_history_json or [])
    history.append(
        {
            "saved_at": timezone.now().isoformat(),
            "note": note,
            "title": venue_map.title,
            "html_markup": venue_map.html_markup,
            "css_stylesheet": venue_map.css_stylesheet,
            "js_script": venue_map.js_script,
        }
    )
    venue_map.revision_history_json = history[-30:]
