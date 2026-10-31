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
    {"div", "span", "section", "header", "footer", "h1", "h2", "h3", "p", "table", "tr", "td", "th"}
)


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
    cleaned = bleach.clean(html or "", tags=ALLOWED_TAGS, strip=True)
    if "<script" in (html or "").lower():
        raise TemplateValidationException("Script tags are not allowed in templates.")
    return cleaned


def lint_required_placeholders(html: str, css: str = "") -> None:
    combined = (html or "") + (css or "")
    missing = [p for p in REQUIRED_PLACEHOLDERS if p not in combined]
    if missing:
        raise TemplateValidationException(f"Missing required placeholders: {', '.join(missing)}")
