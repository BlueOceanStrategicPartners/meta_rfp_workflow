from apps.designer_studio.finalize_validation import (
    collect_html_tag_balance_issues,
    run_systematic_finalize_validation,
)
from apps.designer_studio.models import ALL_BINDING_PLACEHOLDERS
from apps.designer_studio.template_repair_hints import format_repair_brief, repair_pool_hints
from apps.designer_studio.template_workspace import TemplateWorkspace


def _minimal_html(extra: str = "") -> str:
    tokens = " ".join(ALL_BINDING_PLACEHOLDERS)
    return f"<main>{extra} {tokens}</main>"


def test_tag_balance_detects_unclosed_section():
    html = "<section><div>ok</div>"
    issues = collect_html_tag_balance_issues(html)
    assert any("section" in i.lower() for i in issues)


def test_finalize_validation_merges_deterministic_and_structure():
    ws = TemplateWorkspace(
        html_markup="<section><div>broken",
        css_stylesheet=".proposal-cta{display:none}",
        js_script="",
    )
    review = run_systematic_finalize_validation(workspace=ws, message="show accept button")
    assert review["valid"] is False
    assert review["issues"]
    assert review["deterministic_issues"] or review["structure_issues"]


def test_repair_pool_hints_include_replace_lines():
    ws = TemplateWorkspace(
        html_markup=_minimal_html('<section class="hero">Hero</section>'),
        css_stylesheet=".proposal-cta{display:none}",
        js_script="",
    )
    hints = repair_pool_hints(ws, ["Accept CTA hidden by display:none on .proposal-cta"])
    assert hints
    assert hints[0].get("start_line") and hints[0].get("symbol_id")


def test_format_repair_brief_uses_pool_when_workspace_provided():
    ws = TemplateWorkspace(html_markup=_minimal_html(), css_stylesheet=".x{}", js_script="")
    text = format_repair_brief(
        original_message="fix cta",
        issues=["Accept CTA hidden by display:none"],
        workspace=ws,
    )
    assert "list_template_symbols" in text
    assert "replace_lines" in text
