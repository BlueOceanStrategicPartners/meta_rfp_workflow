from apps.designer_studio.template_lint import lint_template_workspace, run_post_edit_validation
from apps.designer_studio.template_workspace import TemplateWorkspace


def test_js_outside_script_reports_line():
    html = """<section>
<h2>Rooms</h2>
document.querySelectorAll('.room-row').forEach(function(el) { el.classList.add('x'); });
</section>"""
    ws = TemplateWorkspace(html_markup=html, css_stylesheet="", js_script="")
    out = lint_template_workspace(ws)
    assert out["valid"] is False
    codes = [d["code"] for d in out["diagnostics"]]
    assert "JS_OUTSIDE_SCRIPT" in codes
    assert any(d["line"] == 3 for d in out["diagnostics"] if d["code"] == "JS_OUTSIDE_SCRIPT")


def test_unclosed_script_reports_start_line():
    html = """<body>
<script>
function render() { return 1; }
<section>Still inside broken script
</body>"""
    ws = TemplateWorkspace(html_markup=html, css_stylesheet="", js_script="")
    out = lint_template_workspace(ws)
    assert out["valid"] is False
    assert any(d["code"] == "UNCLOSED_SCRIPT" for d in out["diagnostics"])


def test_post_edit_validation_merges_gate_and_lint():
    ws = TemplateWorkspace(
        html_markup="<main>{{client_name}}</main>",
        css_stylesheet="",
        js_script="",
    )
    out = run_post_edit_validation(ws, message="test")
    assert "valid" in out
    assert "diagnostics" in out
