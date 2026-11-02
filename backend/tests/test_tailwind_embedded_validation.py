from apps.designer_studio.models import ALL_BINDING_PLACEHOLDERS
from apps.designer_studio.single_file_template import TAILWIND_CDN_SCRIPT
from apps.designer_studio.tailwind_embedded_validation import (
    collect_tailwind_and_embedded_style_issues,
)


def _doc_with_style(css_body: str) -> str:
    tokens = " ".join(ALL_BINDING_PLACEHOLDERS)
    return f"""<!DOCTYPE html>
<html><head>{TAILWIND_CDN_SCRIPT}<style>{css_body}</style></head>
<body class="p-4">{tokens}</body></html>"""


def test_detects_unclosed_css_brace_in_inline_style():
    html = _doc_with_style(".hero-bg { background: #000; .card-lift { transform: scale(1); ")
    issues = collect_tailwind_and_embedded_style_issues(html, "", "")
    assert any("unbalanced" in i.lower() or "unclosed" in i.lower() for i in issues)


def test_detects_literal_close_style_substring_in_css():
    issues = collect_tailwind_and_embedded_style_issues(
        "",
        "body { color: red; }</style>.bad { color: blue; }",
        "",
    )
    assert any("</style>" in i for i in issues)


def test_detects_missing_tailwind_cdn():
    html = "<!DOCTYPE html><html><head></head><body class='p-4'>x</body></html>"
    issues = collect_tailwind_and_embedded_style_issues(html, "", "")
    assert any("tailwind" in i.lower() for i in issues)


def test_detects_css_pasted_as_plain_text_in_body():
    snippet = """Proposal — Elevated Hospitality Experience
body{font-family:Inter,sans-serif;background:#FAF7F0;color:#0B0F1E}
.reveal{opacity:0;transform:translateY(36px)}
.hero-bg{background:linear-gradient(120deg,#0B0F1E 0%,#1a2340 35%)}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-14px)}}
<div class="max-w-7xl mx-auto">Hello</div>
<script>tailwind.config = { theme: { extend: {} } };</script>"""
    issues = collect_tailwind_and_embedded_style_issues(snippet, "", "")
    assert any("plain text" in i.lower() for i in issues)
    assert any("tailwind" in i.lower() and "cdn" in i.lower() for i in issues)


def test_full_document_with_proper_style_tag_passes_loose_css_check():
    html = f"""<!DOCTYPE html><html><head>{TAILWIND_CDN_SCRIPT}
<style>body{{font-family:Inter,sans-serif}}</style></head>
<body class="flex p-4"><div class="text-gold">Hi</div></body></html>"""
    issues = collect_tailwind_and_embedded_style_issues(html, "", "")
    assert not any("plain text" in i.lower() for i in issues)


def test_legacy_js_column_still_flags_loose_css_in_html():
    html = """body{color:red}.reveal{opacity:0}
<div class="max-w-7xl">x</div>"""
    issues = collect_tailwind_and_embedded_style_issues(html, "", "console.log(1);")
    assert any("plain text" in i.lower() for i in issues)
