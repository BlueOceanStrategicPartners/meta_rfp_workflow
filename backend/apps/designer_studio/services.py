from __future__ import annotations

from typing import Any

from apps.core.exceptions import TemplateValidationException
from apps.designer_studio.models import MANDATORY_PLACEHOLDERS
from apps.guardrails.validators import lint_required_placeholders, sanitize_template_html

from .single_file_template import (
    compile_single_file_document,
    effective_style_and_script,
    looks_like_full_html_document,
    template_storage_mode,
)
from .tailwind_embedded_validation import collect_tailwind_and_embedded_style_issues
from .template_alignment import cta_hidden_by_css_issue
from .proposal_bindings import (
    build_binding_replacements,
    compile_html_with_bindings,
    inject_proposal_binding_runtime,
    load_proposal_binding_seed,
)
from .placeholder_guidance import collect_placeholder_binding_issues
from .template_text_quality import (
    collect_bad_proposal_link_issues,
    collect_literal_escape_sequence_issues,
)
from .layout_spacing_validation import collect_trailing_whitespace_issues

def build_preview_replacements(cards: dict | None = None) -> dict[str, str]:
    """JSON binding strings from seed or cards (Designer preview hydrates via runtime JS)."""
    if cards:
        return build_binding_replacements(cards, use_seed_if_empty=True)
    seed = load_proposal_binding_seed()
    empty_cards = {
        "event_overview": seed.get("event_overview") or {},
        "room_block": {},
        "meeting_space": seed.get("meeting_space_specs") or {},
    }
    return build_binding_replacements(empty_cards, use_seed_if_empty=True)


def compile_template(
    html: str,
    css: str = "",
    *,
    js_script: str = "",
    replacements: dict[str, str] | None = None,
    cards: dict | None = None,
    quote: Any | None = None,
    use_seed_if_empty: bool = True,
) -> str:
    """Replace placeholders and build a full HTML document for preview."""
    if replacements is not None:
        mapping = replacements
        body = html or ""
        for token, value in mapping.items():
            body = body.replace(token, value)
    else:
        body = compile_html_with_bindings(
            html or "",
            cards,
            quote=quote,
            use_seed_if_empty=use_seed_if_empty,
        )
    if template_storage_mode(html, css, js_script) == "single":
        doc = compile_single_file_document(body, replacements={})
        return inject_proposal_binding_runtime(doc)
    style_block = f"<style>{css or ''} html,body{{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;}}</style>" if css else (
        "<style>html,body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:0;}</style>"
    )
    script_block = f"<script>{js_script or ''}</script>" if js_script else ""
    doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"{style_block}</head><body>{body}{script_block}</body></html>"
    )
    return inject_proposal_binding_runtime(doc)


def deterministic_template_checks(html: str, css: str = "", js_script: str = "") -> list[str]:
    issues: list[str] = []
    eff_css, eff_js = effective_style_and_script(html, css, js_script)
    try:
        lint_required_placeholders(html, eff_css)
    except TemplateValidationException as exc:
        issues.append(str(exc))

    try:
        mode = template_storage_mode(html, css, js_script)
        if not (mode == "single" and looks_like_full_html_document(html)):
            sanitize_template_html(html, css=css, js_script=js_script)
    except TemplateValidationException as exc:
        issues.append(str(exc))

    issues.extend(collect_tailwind_and_embedded_style_issues(html, css, js_script))
    issues.extend(collect_literal_escape_sequence_issues(html))
    issues.extend(collect_bad_proposal_link_issues(html))
    issues.extend(collect_placeholder_binding_issues(html))
    issues.extend(collect_trailing_whitespace_issues(html, eff_css or css or ""))

    try:
        from apps.guardrails.validators import sanitize_template_js

        sanitize_template_js(eff_js)
    except TemplateValidationException as exc:
        issues.append(str(exc))

    combined = (html or "") + (eff_css or "")
    lower = combined.lower()
    if "proposal-cta" not in lower and "{{cta_accept_button}}" not in (html or ""):
        issues.append(
            "Accept CTA region missing: include {{cta_accept_button}} or a .proposal-cta element."
        )
    cta_hidden = cta_hidden_by_css_issue(eff_css or "", html or "")
    if cta_hidden:
        issues.append(cta_hidden)

    missing_in_html = [p for p in MANDATORY_PLACEHOLDERS if p not in (html or "")]
    if missing_in_html and not issues:
        issues.append(f"Placeholders should appear in HTML body: {', '.join(missing_in_html)}")

    return issues
