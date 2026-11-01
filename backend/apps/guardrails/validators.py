import re
from decimal import Decimal

import bleach

from apps.core.exceptions import FloorPriceBreachAttemptError, TemplateValidationException
from apps.designer_studio.models import REQUIRED_PLACEHOLDERS

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
    re.compile(r"<\s*script", re.I),
]


def validate_negotiation_text(text: str) -> None:
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text or ""):
            raise FloorPriceBreachAttemptError("Blocked adversarial negotiation pattern.")


def enforce_floor_price(offer: Decimal, floor: Decimal) -> None:
    if offer < floor:
        raise FloorPriceBreachAttemptError(
            f"Offer {offer} is below walk-away floor {floor}."
        )


def sanitize_template_html(html: str) -> str:
    cleaned = bleach.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    if "<script" in (html or "").lower():
        raise TemplateValidationException(
            "Inline script tags belong in js_script, not html_markup."
        )
    return cleaned


def sanitize_template_js(js: str) -> str:
    script = (js or "").strip()
    if not script:
        return ""
    for pattern in FORBIDDEN_JS_PATTERNS:
        if pattern.search(script):
            raise TemplateValidationException("Unsafe JavaScript pattern detected in js_script.")
    return script


def lint_required_placeholders(html: str, css: str = "") -> None:
    combined = (html or "") + (css or "")
    missing = [p for p in REQUIRED_PLACEHOLDERS if p not in combined]
    if missing:
        raise TemplateValidationException(f"Missing required placeholders: {', '.join(missing)}")
