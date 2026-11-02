import re
from decimal import Decimal

import bleach

from apps.core.exceptions import FloorPriceBreachAttemptError, TemplateValidationException
from apps.designer_studio.models import MANDATORY_PLACEHOLDERS, OPTIONAL_PLACEHOLDERS

INJECTION_PATTERNS = [
    re.compile(r"system\s+override", re.I),
    re.compile(r"ignore\s+previous\s+instructions", re.I),
    re.compile(r"approve\s+\$\s*1", re.I),
]

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(
    {
        "div",
        "span",
        "section",
        "header",
        "footer",
        "h1",
        "h2",
        "h3",
        "p",
        "table",
        "tr",
        "td",
        "th",
        "img",
        "video",
        "source",
        "figure",
        "figcaption",
        "picture",
        "main",
        "article",
        "button",
    }
)

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "style", "role", "aria-label"],
    "img": ["src", "alt", "width", "height", "loading"],
    "video": ["src", "controls", "poster", "width", "height", "playsinline", "muted", "loop"],
    "source": ["src", "type"],
    "a": ["href", "title", "target", "rel"],
    "button": ["type", "disabled"],
}

FORBIDDEN_JS_PATTERNS = [
    re.compile(r"\beval\s*\(", re.I),
    re.compile(r"new\s+Function\s*\(", re.I),
    re.compile(r"document\.cookie", re.I),
]

FORBIDDEN_JS_PATTERNS_LEGACY_COLUMN = FORBIDDEN_JS_PATTERNS + [
    re.compile(r"<\s*script", re.I),
]


def _is_single_file_proposal_html(html: str, css: str = "", js_script: str = "") -> bool:
    from apps.designer_studio.single_file_template import (
        looks_like_full_html_document,
        template_storage_mode,
    )

    doc = html or ""
    if not looks_like_full_html_document(doc):
        return False
    if template_storage_mode(doc, css, js_script) == "single":
        return True
    if "cdn.tailwindcss.com" in doc.lower() and not (css or "").strip():
        return True
    return False


def sanitize_template_html(html: str, *, css: str = "", js_script: str = "") -> str:
    """Legacy fragments: bleach + no inline scripts. Single-file Tailwind: preserve full document."""
    raw = html or ""
    if _is_single_file_proposal_html(raw, css, js_script):
        from apps.designer_studio.single_file_template import extract_inline_scripts

        inline_js = extract_inline_scripts(raw)
        if inline_js.strip():
            sanitize_template_js(inline_js, allow_script_tags=True)
        return raw

    cleaned = bleach.clean(
        raw,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    if "<script" in raw.lower():
        raise TemplateValidationException(
            "Inline script tags belong in js_script, not html_markup."
        )
    return cleaned


def sanitize_template_js(js: str, *, allow_script_tags: bool = False) -> str:
    script = (js or "").strip()
    if not script:
        return ""
    patterns = FORBIDDEN_JS_PATTERNS if allow_script_tags else FORBIDDEN_JS_PATTERNS_LEGACY_COLUMN
    for pattern in patterns:
        if pattern.search(script):
            raise TemplateValidationException("Unsafe JavaScript pattern detected in js_script.")
    return script


def validate_negotiation_text(text: str) -> None:
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text or ""):
            raise FloorPriceBreachAttemptError("Blocked adversarial negotiation pattern.")


def enforce_floor_price(offer: Decimal, floor: Decimal) -> None:
    if offer < floor:
        raise FloorPriceBreachAttemptError(
            f"Offer {offer} is below walk-away floor {floor}."
        )


def lint_required_placeholders(html: str, css: str = "") -> None:
    combined = (html or "") + (css or "")
    missing = [p for p in MANDATORY_PLACEHOLDERS if p not in combined]
    if missing:
        raise TemplateValidationException(f"Missing required placeholders: {', '.join(missing)}")
    for token in OPTIONAL_PLACEHOLDERS:
        count = (html or "").count(token)
        if count > 1:
            raise TemplateValidationException(
                f"Optional placeholder {token} must appear at most once (found {count})."
            )
