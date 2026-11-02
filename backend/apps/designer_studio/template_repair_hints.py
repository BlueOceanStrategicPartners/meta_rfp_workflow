"""Map validation issue text to scoped search hints for tool-loop repair."""
from __future__ import annotations

import re


def repair_search_hints(issues: list[str]) -> list[dict[str, str]]:
    """Return suggested search_template calls derived from issue messages."""
    hints: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(file: str, query: str) -> None:
        key = (file, query)
        if key in seen:
            return
        seen.add(key)
        hints.append({"file": file, "query": query})

    for issue in issues:
        lower = issue.lower()
        if "cta" in lower or "accept" in lower or "proposal-cta" in lower:
            add("css", "proposal-cta")
            add("css", "display:none")
            add("html", "cta_accept_button")
        if "placeholder" in lower or "{{" in issue:
            for token in re.findall(r"\{\{[^}]+\}\}", issue):
                add("html", token)
        if "js" in lower or "script" in lower or "onclick" in lower:
            add("js", "onclick")
            add("html", "onclick")
        if "map" in lower or "venue-map" in lower:
            add("html", "venue-map")
            add("html", "selected_map_svg")
        if "responsive" in lower or "breakpoint" in lower or "mobile" in lower:
            add("css", "@media")
        if "date" in lower or "iso" in lower or "mm/dd" in lower:
            add("html", "event_dates")
            add("html", "2026-")

    if not hints:
        add("html", "{{")
    return hints[:8]


def format_repair_brief(*, original_message: str, issues: list[str]) -> str:
    lines = [
        "VALIDATION REPAIR PASS — fix ONLY the listed issues using tools.",
        "Do not redesign unrelated sections. Preserve every {{placeholder}} exactly once.",
        "Do not revert the user's layout request (alignment, centering, header button sizing) unless an issue explicitly requires it.",
        "",
        "Issues to fix:",
    ]
    lines.extend(f"- {i}" for i in issues[:12])
    hints = repair_search_hints(issues)
    if hints:
        lines.append("")
        lines.append("Suggested searches (start here):")
        for h in hints:
            lines.append(f"- search_template file={h['file']} query={h['query']!r}")
    if original_message.strip():
        lines.append("")
        lines.append(f"Original user request (context):\n{original_message.strip()[:1500]}")
    return "\n".join(lines)
