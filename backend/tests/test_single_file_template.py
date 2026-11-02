from apps.designer_studio.services import compile_template
from apps.designer_studio.single_file_template import (
    PROPOSAL_SINGLE_FILE_SCAFFOLD,
    template_storage_mode,
)


def test_template_storage_mode_single_when_css_js_empty():
    assert template_storage_mode("<html></html>", "", "") == "single"
    assert template_storage_mode("<html></html>", "a{}", "") == "legacy"


def test_compile_single_file_includes_tailwind_and_placeholders():
    html = PROPOSAL_SINGLE_FILE_SCAFFOLD
    compiled = compile_template(html, "", js_script="")
    assert "cdn.tailwindcss.com" in compiled
    assert "Acme Corporation" in compiled
    assert "<!DOCTYPE html>" in compiled.upper() or "<!doctype html>" in compiled.lower()
