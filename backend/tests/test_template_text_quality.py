from apps.designer_studio.template_text_quality import (
    collect_bad_proposal_link_issues,
    collect_literal_escape_sequence_issues,
)


def test_detects_literal_u2022_in_visible_html():
    html = '<span class="badge">7 ZONES \\U2022 HOVER MARKERS</span>'
    issues = collect_literal_escape_sequence_issues(html)
    assert issues
    assert "\\U2022" in issues[0] or "u2022" in issues[0].lower()


def test_allows_real_bullet_character():
    html = "<span>7 ZONES • HOVER MARKERS</span>"
    assert not collect_literal_escape_sequence_issues(html)


def test_ignores_escapes_inside_script():
    html = "<script>const s = '\\u2022';</script><p>OK</p>"
    assert not collect_literal_escape_sequence_issues(html)


def test_flags_app_route_hrefs():
    html = '<a href="/rooms">Rooms</a><a href="#hero">Hero</a>'
    issues = collect_bad_proposal_link_issues(html)
    assert len(issues) == 1
    assert "/rooms" in issues[0]
