from apps.designer_studio.template_alignment import (
    cta_hidden_by_css_issue,
    collect_alignment_issues,
    user_wants_us_dates,
)


def test_cta_check_ignores_map_popup_hidden():
    css = (
        ".map-popup.hidden{display:none;}"
        ".proposal-cta{background:#c9a227;color:#fff;padding:0.5rem 1rem;}"
    )
    assert cta_hidden_by_css_issue(css) is None


def test_cta_check_flags_hidden_accept_button():
    css = ".proposal-cta{display:none;}"
    assert cta_hidden_by_css_issue(css) is not None


def test_us_date_alignment_flags_iso_in_copy():
    issues = collect_alignment_issues(
        message="Use US style dates MM/DD/YYYY",
        history=[],
        html="<p>Event 2026-06-01 — 2026-06-04</p><div>{{event_dates}}</div>",
    )
    assert any("U.S." in i or "ISO" in i for i in issues)


def test_user_wants_us_dates():
    assert user_wants_us_dates("luxury proposal with U.S. style dating")
