"""Tailwind single-file proposals: lint embedded <style> CSS and document setup.

Legacy css_stylesheet/js_script columns are empty; utilities use Tailwind CDN plus optional
inline <style> for custom rules. A small CSS syntax error in <style> often breaks all
rules after the mistake — validate_template must catch these.
"""
from __future__ import annotations

import re
from typing import Any

from .single_file_template import (
    TAILWIND_CDN_SCRIPT,
    extract_inline_styles,
    looks_like_full_html_document,
    template_storage_mode,
)

_STYLE_BLOCK_RE = re.compile(
    r"<style(?P<attrs>[^>]*)>(?P<body>.*?)</style>",
    re.DOTALL | re.IGNORECASE,
)

# Theme / proposal CSS leaked as text nodes (common agent mistake).
_LOOSE_CSS_RULE = re.compile(
    r"(?:^|[\s>])(?:body|html)\s*\{|[@.]?(?:keyframes|font-face)\s+[\w-]+\s*\{|\.[\w-]+\s*\{[^}]{4,}\}",
    re.IGNORECASE | re.MULTILINE,
)
_TAILWIND_UTILITY_CLASS = re.compile(
    r'class="[^"]*(?:\b(?:flex|grid|max-w-|min-h-|bg-|text-|rounded|px-|py-|md:|lg:|hover:)[^"]*)"',
    re.IGNORECASE,
)


def _html_without_style_and_script(html: str) -> str:
    text = html or ""
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.I | re.S)
    return text


def _text_outside_tags(html: str) -> str:
    """Rough text content when CSS was pasted outside markup tags."""
    stripped = _html_without_style_and_script(html)
    return re.sub(r"<[^>]+>", "\n", stripped)


def _loose_css_in_markup_issues(html: str) -> list[str]:
    """Detect CSS rules sitting in the body as plain text (not in <style>)."""
    issues: list[str] = []
    doc = html or ""
    if not doc.strip():
        return issues

    text_blob = _text_outside_tags(doc)
    if not text_blob.strip():
        return issues

    rule_hits = list(_LOOSE_CSS_RULE.finditer(text_blob))
    if not rule_hits:
        return issues

    theme_markers = (
        "@keyframes",
        ".hero-bg",
        ".reveal",
        ".map-stage",
        ".gold-shimmer",
        "font-family:Inter",
        "background-clip:text",
    )
    blob_lower = text_blob.lower()
    looks_like_theme_css = any(m in blob_lower for m in theme_markers) or len(rule_hits) >= 4

    if not looks_like_theme_css:
        return issues

    first = rule_hits[0]
    line_in_text = text_blob[: first.start()].count("\n") + 1
    issues.append(
        "Custom CSS is pasted as plain text in html_markup (not inside <style>...</style>). "
        "The browser will not apply these rules — wrap the entire theme block in "
        "<head><style>…</style></head> or move it into a single <style> tag before <body>. "
        f"First loose rule near text line ~{line_in_text} (e.g. {first.group(0)[:48].strip()}…)."
    )
    return issues


def _tailwind_fragment_issues(html: str) -> list[str]:
    """Tailwind utilities / tailwind.config without CDN in stored markup."""
    issues: list[str] = []
    doc = html or ""
    lower = doc.lower()
    if "cdn.tailwindcss.com" in lower:
        return issues
    uses_config = "tailwind.config" in lower
    uses_utilities = bool(_TAILWIND_UTILITY_CLASS.search(doc))
    if uses_config:
        issues.append(
            "Found tailwind.config in <script> but no Tailwind CDN script — utility classes "
            "(flex, bg-gold, max-w-7xl, etc.) will not render. Add "
            '<script src="https://cdn.tailwindcss.com"></script> in <head> before the config script.'
        )
    elif uses_utilities and not looks_like_full_html_document(doc):
        issues.append(
            "html_markup uses Tailwind utility classes but is not a full HTML document with "
            "Tailwind CDN in <head>. Use a single-file <!DOCTYPE html> scaffold with "
            "cdn.tailwindcss.com, <style> for custom theme CSS, then your sections in <body>."
        )
    elif uses_utilities and looks_like_full_html_document(doc):
        issues.append(
            "Tailwind utility classes present but cdn.tailwindcss.com is missing from <head>."
        )
    return issues


def _line_number_at(text: str, index: int) -> int:
    return text.count("\n", 0, max(0, index)) + 1


def _css_balance_issues(css: str, *, label: str) -> list[str]:
    issues: list[str] = []
    if not (css or "").strip():
        return issues

    if re.search(r"</style\s*>", css, flags=re.I):
        issues.append(
            f"{label}: contains a literal '</style>' inside CSS — the browser closes the "
            "<style> block early and drops remaining custom styles (Tailwind utilities may still work)."
        )

    depth = 0
    paren = 0
    bracket = 0
    in_str: str | None = None
    i = 0
    n = len(css)
    error_at: int | None = None

    while i < n:
        ch = css[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            if end < 0:
                issues.append(f"{label}: unclosed CSS comment /* …")
                break
            i = end + 2
            continue
        if ch in ("'", '"'):
            in_str = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                error_at = i
                issues.append(f"{label}: unexpected '}}' in CSS (styles after this may not apply).")
                break
        elif ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
            if paren < 0:
                issues.append(f"{label}: unexpected ')' in CSS.")
                break
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket -= 1
            if bracket < 0:
                issues.append(f"{label}: unexpected ']' in CSS selector.")
                break
        i += 1

    if in_str and not issues:
        issues.append(f"{label}: unclosed string literal in CSS.")
    elif depth > 0 and not issues:
        issues.append(
            f"{label}: unbalanced '{{' — {depth} unclosed brace(s); "
            "rules after the error are ignored by the browser."
        )
    elif paren > 0 and not issues:
        issues.append(f"{label}: unclosed '(' in CSS value.")
    elif bracket > 0 and not issues:
        issues.append(f"{label}: unclosed '[' in CSS selector.")

    # Obvious broken declarations (common in minified theme blocks)
    if re.search(r"[\w-]+\s*:\s*;", css):
        issues.append(f"{label}: empty CSS property value (property:;) — check custom theme styles.")
    if re.search(r"[\w-]+\s*:\s*}", css):
        issues.append(f"{label}: CSS property missing value before '}}'.")

    if error_at is not None and len(issues) == 1:
        line = css[:error_at].count("\n") + 1
        issues[-1] = issues[-1] + f" (near line {line} in block)"

    return issues


def _tailwind_setup_issues(html: str) -> list[str]:
    issues: list[str] = []
    doc = html or ""
    if not looks_like_full_html_document(doc):
        return issues
    lower = doc.lower()
    if "cdn.tailwindcss.com" not in lower and "tailwindcss" not in lower:
        issues.append(
            "Tailwind CDN script missing from <head> — utility classes will not apply. "
            f"Add: {TAILWIND_CDN_SCRIPT.strip()}"
        )
    return issues


def _style_block_semantic_issues(html: str) -> list[str]:
    issues: list[str] = []
    lower_html = html or ""
    idx = 0
    while True:
        start = lower_html.find("<style", idx)
        if start < 0:
            break
        gt = lower_html.find(">", start)
        if gt < 0:
            issues.append("Unclosed <style> tag — custom CSS may not load.")
            break
        attrs = lower_html[start:gt]
        open_end = gt + 1
        close = lower_html.find("</style>", open_end)
        if close < 0:
            line = _line_number_at(html, start)
            issues.append(
                f"Unclosed <style> starting HTML line {line} — styles after this point may not apply."
            )
            break
        body = (html or "")[open_end:close]
        start_line = _line_number_at(html, start)
        label = f"Inline <style> starting HTML line {start_line}"
        issues.extend(_css_balance_issues(body, label=label))
        if "@apply" in body and "text/tailwindcss" not in attrs.lower():
            issues.append(
                f"{label}: uses @apply in a plain <style> tag — Tailwind CDN only processes @apply "
                'inside <style type="text/tailwindcss">. Move @apply there or use utility classes on HTML.'
            )
        if re.search(r"@import\s", body, flags=re.I):
            issues.append(
                f"{label}: @import inside inline <style> often fails in proposal preview — prefer "
                "link tags in <head> or Tailwind utilities."
            )
        idx = close + len("</style>")
    opens = len(re.findall(r"<\s*style\b", html or "", flags=re.I))
    closes = len(re.findall(r"<\s*/\s*style\s*>", html or "", flags=re.I))
    if opens > closes:
        issues.append(
            f"Unclosed <style> tag ({opens} open vs {closes} close) — custom CSS and layout may break."
        )
    return issues


def collect_tailwind_and_embedded_style_issues(
    html: str,
    css: str = "",
    js_script: str = "",
) -> list[str]:
    """Tailwind + embedded/loose CSS checks on html_markup (always) plus legacy css column."""
    mode = template_storage_mode(html, css, js_script)
    issues: list[str] = []

    # Always inspect html_markup — agents often paste theme CSS as body text even when js_script is set.
    issues.extend(_tailwind_fragment_issues(html))
    issues.extend(_loose_css_in_markup_issues(html))
    if looks_like_full_html_document(html):
        issues.extend(_tailwind_setup_issues(html))
        issues.extend(_style_block_semantic_issues(html))
    elif extract_inline_styles(html).strip():
        issues.extend(
            _css_balance_issues(extract_inline_styles(html), label="Inline CSS in html fragment")
        )

    if mode == "legacy":
        if (css or "").strip():
            issues.extend(_css_balance_issues(css, label="css_stylesheet"))
        if (js_script or "").strip() and _loose_css_in_markup_issues(html):
            issues.append(
                "js_script column is populated while html_markup still contains loose CSS text — "
                "use one single-file HTML document: <head> with Tailwind CDN + <style>, "
                "<body> markup only, inline <script> at end; clear css_stylesheet and js_script."
            )
        seen: set[str] = set()
        unique: list[str] = []
        for item in issues:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    if (css or "").strip() or (js_script or "").strip():
        issues.append(
            "Template uses single-file Tailwind HTML but css_stylesheet/js_script columns are non-empty — "
            "move styles/scripts into html_markup <style>/<script> and clear legacy fields."
        )

    seen: set[str] = set()
    unique: list[str] = []
    for item in issues:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def collect_tailwind_and_embedded_style_report(
    html: str,
    css: str = "",
    js_script: str = "",
) -> dict[str, Any]:
    issues = collect_tailwind_and_embedded_style_issues(html, css, js_script)
    return {
        "valid": not issues,
        "issues": issues,
        "storage_mode": template_storage_mode(html, css, js_script),
    }
