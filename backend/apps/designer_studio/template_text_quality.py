"""Visible copy quality checks for proposal HTML (labels, badges, nav text)."""
from __future__ import annotations

import re

_LITERAL_ESCAPE_RE = re.compile(r"\\[uU][0-9a-fA-F]{4,8}|\\x[0-9a-fA-F]{2}")

_BAD_PROPOSAL_HREF_RE = re.compile(
    r"""href\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)

_ALLOWED_HREF_PREFIXES = ("#", "mailto:", "tel:", "javascript:")


def _href_is_allowed(target: str) -> bool:
    t = (target or "").strip()
    if not t:
        return False
    lower = t.lower()
    if lower.startswith(_ALLOWED_HREF_PREFIXES):
        return True
    if lower.startswith("http://") or lower.startswith("https://"):
        return True
    return False


def collect_bad_proposal_link_issues(html: str, *, max_reports: int = 8) -> list[str]:
    """In-proposal navigation must use #section anchors — not app paths like /rooms."""
    body = html or ""
    issues: list[str] = []
    seen: set[str] = set()
    for match in _BAD_PROPOSAL_HREF_RE.finditer(body):
        href = match.group(1).strip()
        if _href_is_allowed(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        issues.append(
            f'Link href="{href}" navigates away from the proposal (Designer preview loads RFP Engine '
            f'routes like /client or /designer). Use href="#section-id" matching <section id="…"> '
            f'or full https:// for external URLs only.'
        )
        if len(issues) >= max_reports:
            break
    return issues


def _strip_script_and_style(html: str) -> str:
    text = html or ""
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.I | re.S)
    return text


def collect_literal_escape_sequence_issues(html: str, *, max_reports: int = 6) -> list[str]:
    """Detect Python-style \\u2022 / \\U2022 in guest-visible HTML text (shows as garbage)."""
    visible = _strip_script_and_style(html)
    issues: list[str] = []
    seen: set[str] = set()
    for match in _LITERAL_ESCAPE_RE.finditer(visible):
        token = match.group(0)
        if token in seen:
            continue
        seen.add(token)
        snippet = visible[max(0, match.start() - 24) : match.end() + 24].replace("\n", " ")
        issues.append(
            f"Visible text contains literal escape {token!r} (guests see backslash-u garbage). "
            f"Use the real Unicode character (e.g. •) or HTML entity (&#8226;), never \\u2022 in labels. "
            f"Context: …{snippet}…"
        )
        if len(issues) >= max_reports:
            break
    return issues
