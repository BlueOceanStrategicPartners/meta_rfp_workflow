"""Live preview point-to-select — agent context + chat history display."""
from __future__ import annotations

from typing import Any


def format_preview_target_for_agent(target: dict[str, Any]) -> str:
    section_label = str(target.get("sectionLabel") or target.get("section_label") or "—")
    section_id = str(target.get("sectionId") or target.get("section_id") or "").strip()
    tag = str(target.get("tag") or "section")
    el_id = str(target.get("id") or "").strip()
    classes = str(target.get("classSummary") or target.get("class_summary") or "").strip()
    snippet = str(target.get("textSnippet") or target.get("text_snippet") or "").strip()
    selector = str(target.get("selectorHint") or target.get("selector_hint") or "").strip()

    lines = [
        "[Live preview target — scope your edit to THIS region in html_markup]",
        f"- Section: {section_label}"
        + (f" (#{section_id})" if section_id else ""),
        f"- Element: <{tag}" + (f' id="{el_id}"' if el_id else "") + ">",
    ]
    if classes:
        lines.append(f"- Classes: {classes}")
    if snippet:
        lines.append(f"- Visible text: {snippet[:160]}")
    if selector:
        lines.append(f"- Find in template: {selector}")
    lines.append("Do not redesign unrelated sections unless the user asks.")
    return "\n".join(lines)


def expand_user_turn_content_for_agent(turn: dict[str, Any]) -> str:
    """Rebuild full agent-facing user text from display content + structured preview target."""
    content = str(turn.get("content") or "").strip()
    target = turn.get("preview_target")
    if not isinstance(target, dict) or not target:
        return content
    block = format_preview_target_for_agent(target)
    if content:
        return f"{block}\n\n{content}"
    return block
