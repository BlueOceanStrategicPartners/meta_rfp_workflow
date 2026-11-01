"""Proposal template sample injection and deterministic validation."""
from __future__ import annotations

from apps.core.exceptions import TemplateValidationException
from apps.designer_studio.models import REQUIRED_PLACEHOLDERS
from apps.guardrails.validators import lint_required_placeholders, sanitize_template_html

SAMPLE_REPLACEMENTS = {
    "{{client_name}}": "Acme Corporation",
    "{{event_dates}}": "2026-06-01 — 2026-06-04",
    "{{verified_room_blocks}}": (
        "<table><tr><th>Date</th><th>Rooms</th></tr>"
        "<tr><td>2026-06-01</td><td>60 King</td></tr>"
        "<tr><td>2026-06-02</td><td>60 King</td></tr></table>"
    ),
    "{{selected_map_svg}}": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120">'
        '<rect x="10" y="10" width="180" height="100" fill="rgba(0,180,255,0.15)" stroke="#0af"/>'
        "</svg>"
    ),
    "{{meeting_space_specs}}": "Grand Sapphire Ballroom · Classroom · 250 guests",
    "{{xgboost_quote_breakdown}}": (
        "Floor $42,000 · Target $48,500 · Anchor $52,000"
    ),
    "{{negotiated_concessions}}": "Complimentary AV upgrade · Late checkout for VIP suite",
    "{{cta_accept_button}}": (
        '<button type="button" class="proposal-cta">Accept Proposal</button>'
    ),
}


def build_preview_replacements() -> dict[str, str]:
    """Sample data for designer preview — uses live default venue map when available."""
    from .venue_map_context import default_map_embed_for_proposal

    mapping = dict(SAMPLE_REPLACEMENTS)
    embed = default_map_embed_for_proposal()
    if embed:
        mapping["{{selected_map_svg}}"] = embed
    return mapping


def compile_template(
    html: str,
    css: str = "",
    *,
    js_script: str = "",
    replacements: dict[str, str] | None = None,
    use_default_venue_map: bool = True,
) -> str:
    """Replace placeholders and build a full HTML document for preview."""
    if replacements is not None:
        mapping = replacements
    elif use_default_venue_map:
        mapping = build_preview_replacements()
    else:
        mapping = SAMPLE_REPLACEMENTS
    body = html or ""
    for token, value in mapping.items():
        body = body.replace(token, value)
    style_block = f"<style>{css or ''} html,body{{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;}}</style>" if css else (
        "<style>html,body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:0;}</style>"
    )
    script_block = f"<script>{js_script or ''}</script>" if js_script else ""
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"{style_block}</head><body>{body}{script_block}</body></html>"
    )


def deterministic_template_checks(html: str, css: str = "", js_script: str = "") -> list[str]:
    issues: list[str] = []
    try:
        lint_required_placeholders(html, css)
    except TemplateValidationException as exc:
        issues.append(str(exc))

    try:
        sanitize_template_html(html)
    except TemplateValidationException as exc:
        issues.append(str(exc))

    try:
        from apps.guardrails.validators import sanitize_template_js

        sanitize_template_js(js_script)
    except TemplateValidationException as exc:
        issues.append(str(exc))

    combined = (html or "") + (css or "")
    lower = combined.lower()
    if "proposal-cta" not in lower and "{{cta_accept_button}}" not in (html or ""):
        issues.append(
            "Accept CTA region missing: include {{cta_accept_button}} or a .proposal-cta element."
        )
    if "display:none" in lower.replace(" ", "") and "cta" in lower:
        issues.append("CTA may be hidden via display:none; ensure the accept button is visible.")

    missing_in_html = [p for p in REQUIRED_PLACEHOLDERS if p not in (html or "")]
    if missing_in_html and not issues:
        issues.append(f"Placeholders should appear in HTML body: {', '.join(missing_in_html)}")

    return issues
