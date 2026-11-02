from __future__ import annotations

from apps.inventory.models import SpaceInventory


def _suggest_alternative_spaces(
    headcount: int, seating_style: str, property_id
) -> list[SpaceInventory]:
    spaces = SpaceInventory.objects.filter(property_id=property_id)
    result: list[SpaceInventory] = []
    for space in spaces:
        cap = (space.capacities_json or {}).get(seating_style) or (
            space.capacities_json or {}
        ).get("classroom", 0)
        if cap and cap >= headcount:
            result.append(space)
    return result[:3]
