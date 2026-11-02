import pytest

from apps.core.exceptions import TemplateValidationException
from apps.designer_studio.models import MANDATORY_PLACEHOLDERS
from apps.designer_studio.services import deterministic_template_checks
from apps.guardrails.validators import lint_required_placeholders


def _mandatory_html() -> str:
    return "".join(f"<div>{p}</div>" for p in MANDATORY_PLACEHOLDERS)


def test_lint_allows_template_without_map():
    html = _mandatory_html()
    lint_required_placeholders(html, "body{margin:0;}")


def test_lint_rejects_missing_mandatory_token():
    html = _mandatory_html().replace("{{client_name}}", "")
    with pytest.raises(TemplateValidationException, match="Missing required placeholders"):
        lint_required_placeholders(html)


def test_deterministic_checks_pass_without_map():
    html = _mandatory_html() + "{{cta_accept_button}}"
    css = "body{margin:0;} .proposal-cta{display:block;}"
    issues = deterministic_template_checks(html, css, "")
    assert not any("selected_map_svg" in i for i in issues)
