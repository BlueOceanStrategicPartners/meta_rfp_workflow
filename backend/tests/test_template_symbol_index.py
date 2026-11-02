from apps.designer_studio.template_workspace import TemplateWorkspace
from apps.designer_studio.template_symbol_index import (
    execute_list_template_symbols,
    execute_read_template_symbol,
    index_template_file,
)


def test_list_css_rules():
    ws = TemplateWorkspace(
        html_markup="",
        css_stylesheet="a { color: blue; }\n.header nav a { color: inherit; }",
        js_script="",
    )
    result = execute_list_template_symbols(ws, {"file": "css", "query": "a"})
    assert result["ok"]
    assert result["shown"] >= 1
    names = " ".join(s["name"] for s in result["symbols"])
    assert "a" in names.lower()


def test_read_symbol_roundtrip():
    css = ".hero { padding: 2rem; }\n.footer { margin: 0; }"
    ws = TemplateWorkspace(html_markup="", css_stylesheet=css, js_script="")
    listed = execute_list_template_symbols(ws, {"file": "css", "kind": "css_rule"})
    sym_id = listed["symbols"][0]["id"]
    read = execute_read_template_symbol(ws, {"symbol_id": sym_id})
    assert read["ok"]
    assert ".hero" in read["content"] or "hero" in read["content"]
    assert read["symbol"]["start_line"] >= 1


def test_html_element_symbols():
    ws = TemplateWorkspace(
        html_markup='<header id="top"><nav class="main-nav"><a href="#">x</a></nav></header>',
        css_stylesheet="",
        js_script="",
    )
    syms = index_template_file(ws, "html")
    names = {s.name for s in syms}
    assert "header#top" in names or "#top" in names or ".main-nav" in names


def test_js_function_symbol():
    js = "function initMap() {\n  return 1;\n}\n"
    ws = TemplateWorkspace(html_markup="", css_stylesheet="", js_script=js)
    syms = index_template_file(ws, "js")
    assert any(s.name == "initMap" for s in syms)


def test_list_symbols_semantic_query_ranks_sections():
    html = """<section id="pricing" class="p-4"><h2>Pricing breakdown</h2></section>
<section id="map" class="venue-map-proposal"><h2>Venue floorplan</h2></section>"""
    ws = TemplateWorkspace(html_markup=html, css_stylesheet="", js_script="")
    listed = execute_list_template_symbols(
        ws, {"file": "html", "kind": "proposal_section", "query": "interactive map floorplan"}
    )
    assert listed["ok"]
    assert listed["symbols"][0]["name"].lower().find("map") >= 0 or "venue" in listed["symbols"][0]["name"].lower()

    html = """<!DOCTYPE html><html><body>
<section id="hero" class="p-8"><h1>Welcome</h1></section>
<section class="venue-map-proposal" aria-label="Map">
<div id="venue-map"><script>function initMap(){}</script></div>
</section>
</body></html>"""
    ws = TemplateWorkspace(html_markup=html, css_stylesheet="", js_script="")
    listed = execute_list_template_symbols(ws, {"file": "html", "kind": "proposal_section"})
    assert listed["ok"]
    assert listed["shown"] >= 2
    ids = {s["kind"] for s in listed["symbols"]}
    assert ids == {"proposal_section"}
    map_sym = next(
        s for s in listed["symbols"] if "map" in s["name"].lower() or "venue" in s["name"].lower()
    )
    read = execute_read_template_symbol(ws, {"symbol_id": map_sym["id"]})
    assert read["ok"]
    assert "initMap" in read["content"]
    assert "venue-map" in read["content"]
