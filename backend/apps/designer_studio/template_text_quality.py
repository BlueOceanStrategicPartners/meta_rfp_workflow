"""Visible copy quality checks for proposal HTML (labels, badges, nav text)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from django.conf import settings

_LITERAL_ESCAPE_RE = re.compile(r"\\[uU][0-9a-fA-F]{4,8}|\\x[0-9a-fA-F]{2}")

_BAD_PROPOSAL_HREF_RE = re.compile(
    r"""href\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)

_ALLOWED_NON_HTTP_PREFIXES = ("#", "mailto:", "tel:", "javascript:")

# RFP Engine SPA routes — never use as proposal button targets (any host).
_APP_ROUTE_PATH_PREFIXES = (
    "/client",
    "/designer",
    "/admin",
    "/api",
)

_DEV_APP_HOST_SUFFIXES = (
    "localhost",
    "127.0.0.1",
    "[::1]",
)


def _configured_app_netlocs() -> set[str]:
    netlocs: set[str] = set()
    for suffix in _DEV_APP_HOST_SUFFIXES:
        netlocs.add(suffix)
        netlocs.add(f"{suffix}:5173")
        netlocs.add(f"{suffix}:3000")
        netlocs.add(f"{suffix}:8000")
    raw = getattr(settings, "DESIGNER_PROPOSAL_APP_ORIGINS", "") or ""
    for chunk in str(raw).replace(";", ",").split(","):
        item = chunk.strip()
        if not item:
            continue
        if "://" in item:
            netlocs.add(urlparse(item).netloc.lower())
        else:
            netlocs.add(item.lower())
    extra = getattr(settings, "FRONTEND_URL", "") or getattr(settings, "PUBLIC_FRONTEND_URL", "") or ""
    if extra and "://" in str(extra):
        netlocs.add(urlparse(str(extra)).netloc.lower())
    return netlocs


def _is_proposal_app_netloc(netloc: str) -> bool:
    n = (netloc or "").lower()
    if not n:
        return False
    if n in _configured_app_netlocs():
        return True
    for suffix in _DEV_APP_HOST_SUFFIXES:
        if n == suffix or n.startswith(f"{suffix}:"):
            return True
    return False


def _path_is_rfp_app_route(path: str) -> bool:
    p = (path or "/").split("?")[0].split("#")[0] or "/"
    if p == "/":
        return True
    return any(p == prefix or p.startswith(f"{prefix}/") for prefix in _APP_ROUTE_PATH_PREFIXES)


def _classify_proposal_href(href: str) -> str | None:
    """Return issue text if href must not appear on in-proposal buttons/links."""
    t = (href or "").strip()
    if not t:
        return "Empty href on a link/button — use href=\"#section-id\" matching <section id>."
    lower = t.lower()
    if lower.startswith(_ALLOWED_NON_HTTP_PREFIXES):
        return None
    if lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(t)
        netloc = (parsed.netloc or "").lower()
        path = parsed.path or "/"
        if _is_proposal_app_netloc(netloc):
            return (
                f'Link href="{href}" uses the same domain as the RFP Engine / Designer preview '
                f"({netloc}) — guests leave the proposal and load app routing. "
                f'Use href="#section-id" on <section id="…"> for in-page CTAs only.'
            )
        if _path_is_rfp_app_route(path):
            return (
                f'Link href="{href}" targets an RFP Engine route ({path.split("?")[0]}). '
                f'Use href="#section-id" (e.g. href="#rooms", href="#accept") — not /client, '
                f"/designer, or full URLs to those paths."
            )
        return None
    return (
        f'Link href="{href}" navigates away from the proposal (Designer preview loads RFP Engine '
        f'routes like /client or /designer). Use href="#section-id" matching <section id="…"> '
        f"or a full https:// URL to an external property/marketing site only."
    )


def collect_bad_proposal_link_issues(html: str, *, max_reports: int = 8) -> list[str]:
    """In-proposal navigation must use #section anchors — not app paths or same-origin URLs."""
    body = html or ""
    issues: list[str] = []
    seen: set[str] = set()
    for match in _BAD_PROPOSAL_HREF_RE.finditer(body):
        href = match.group(1).strip()
        issue = _classify_proposal_href(href)
        if not issue or issue in seen:
            continue
        seen.add(issue)
        issues.append(issue)
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
