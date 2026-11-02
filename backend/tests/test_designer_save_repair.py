import pytest

from apps.designer_studio.design_agent import (
    DesignerStudioAgent,
    _filter_save_muse_issues,
)
from apps.designer_studio.models import REQUIRED_PLACEHOLDERS


def test_filter_save_muse_issues_strips_token_noise():
    raw = [
        "compilation is incomplete with 6 unresolved tokens",
        "Accept CTA hidden with display:none on .proposal-cta",
    ]
    filtered = _filter_save_muse_issues(raw)
    assert len(filtered) == 1
    assert "CTA" in filtered[0]


@pytest.mark.django_db
def test_prepare_for_save_passes_with_valid_fixture_html():
    agent = DesignerStudioAgent()
    tokens = "".join(f"<p>{t}</p>" for t in REQUIRED_PLACEHOLDERS)
    html = f"<section>{tokens}<div class='proposal-cta'>{{{{cta_accept_button}}}}</div></section>"
    css = ".proposal-cta{display:block;} @media (max-width:768px){.hero{flex-direction:column;}}"
    prepared = agent.prepare_for_save(html, css, "")
    assert prepared["html_markup"]
    assert "{{client_name}}" in prepared["html_markup"]
