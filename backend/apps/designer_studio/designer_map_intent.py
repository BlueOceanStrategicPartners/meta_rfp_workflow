"""Map-related intent detection for designer work-plan labels (map lives in proposal HTML)."""

MAP_KEYWORDS = (
    "map",
    "floorplan",
    "floor plan",
    "venue layout",
    "interactive map",
    "ballroom",
    "floorplate",
)


def message_has_map_intent(message: str) -> bool:
    lower = (message or "").lower()
    return any(k in lower for k in MAP_KEYWORDS)
