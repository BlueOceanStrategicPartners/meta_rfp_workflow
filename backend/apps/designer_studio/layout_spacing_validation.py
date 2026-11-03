"""Deterministic checks for excess trailing scroll dead space below proposal content."""
from __future__ import annotations

import re

# Tailwind default spacing scale (px) for pb-/py- utilities without brackets.
_TAILWIND_SPACE_PX: dict[int, int] = {
    96: 384,
    80: 320,
    72: 288,
    64: 256,
    52: 208,
    48: 192,
    40: 160,
    32: 128,
    24: 96,
    20: 80,
}

_MIN_H_ARBITRARY = re.compile(r"\bmin-h-\[(\d+)\s*px\]", re.I)
_H_ARBITRARY = re.compile(r"\b(?:h|min-h)-\[(\d+)\s*px\]", re.I)
_MIN_H_UTIL = re.compile(r"\bmin-h-(screen|full|\d+)\b", re.I)
_H_SCREEN = re.compile(r"(?<!(?:min-))h-screen\b", re.I)
_EMPTY_DIV = re.compile(r"<div\b([^>]*)>\s*(?:<!--[\s\S]*?-->\s*)*</div>", re.I)
_SECTION_OPEN = re.compile(r"<section\b([^>]*)>", re.I)
_STRIP_BLOCKS = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)


def _strip_scripts_and_styles(text: str) -> str:
    return _STRIP_BLOCKS.sub("", text or "")


def _body_markup(html: str) -> str:
    text = html or ""
    m = re.search(r"<body\b[^>]*>([\s\S]*)</body>", text, re.I)
    if m:
        return m.group(1)
    return text


def _tailwind_padding_bottom_px(class_attr: str) -> int:
    total = 0
    for util in re.findall(r"\b(?:pb|py)-(\[[^\]]+\]|\d+)\b", class_attr or "", re.I):
        if util.startswith("["):
            px = re.match(r"\[(\d+)\s*px\]", util, re.I)
            if px:
                total = max(total, int(px.group(1)))
            continue
        try:
            total = max(total, _TAILWIND_SPACE_PX.get(int(util), int(util) * 4))
        except ValueError:
            continue
    return total


def _count_pattern(text: str, pattern: re.Pattern[str]) -> int:
    return len(pattern.findall(_strip_scripts_and_styles(text)))


def _tail_after_last_section(html: str) -> str:
    body = _body_markup(html)
    body = _strip_scripts_and_styles(body)
    matches = list(re.finditer(r"</section\s*>", body, re.I))
    if not matches:
        return body[-1200:] if len(body) > 1200 else body
    return body[matches[-1].end() :]


def _collect_stacked_viewport_height_issues(html: str) -> list[str]:
    issues: list[str] = []
    scan = _strip_scripts_and_styles(html)
    min_h_screen = _count_pattern(scan, _MIN_H_UTIL)
    min_h_screen_count = len(re.findall(r"\bmin-h-screen\b", scan, re.I))
    h_screen_count = len(_H_SCREEN.findall(scan))
    if min_h_screen_count >= 2 or (min_h_screen_count >= 1 and h_screen_count >= 1):
        issues.append(
            "Excess trailing whitespace: stacked min-h-screen / h-screen utilities "
            "(body + main/wrapper) force a full extra viewport of empty scroll area — "
            "use min-h-screen on body only; let sections size to content."
        )
    if h_screen_count >= 2:
        issues.append(
            "Excess trailing whitespace: multiple h-screen blocks — remove spacer "
            "sections and height locks below the last content section."
        )
    _ = min_h_screen
    return issues


def _collect_trailing_tail_issues(html: str) -> list[str]:
    issues: list[str] = []
    tail = _tail_after_last_section(html)
    if not tail.strip():
        return issues

    for match in _MIN_H_ARBITRARY.finditer(tail):
        px = int(match.group(1))
        if px >= 480:
            issues.append(
                f"Excess trailing whitespace: min-h-[{px}px] appears after the last "
                f"section — remove empty height fillers; map sections may use min-h-[420px] "
                f"only when the map lives inside that section."
            )
            break

    for match in _EMPTY_DIV.finditer(tail):
        attrs = match.group(1) or ""
        for hm in _H_ARBITRARY.finditer(attrs):
            px = int(hm.group(1))
            if px >= 320:
                issues.append(
                    f"Excess trailing whitespace: empty <div> with h/min-h-[{px}px] "
                    "after the last section — delete spacer divs; do not pad the page bottom."
                )
                return issues

    if re.search(r"\b(?:flex-1|grow)\b", tail, re.I) and not re.search(
        r">\s*[^<\s][^<]{2,}", tail, re.I
    ):
        issues.append(
            "Excess trailing whitespace: flex-1/grow on an empty trailing container — "
            "remove bottom flex spacers; end the page at footer or last section."
        )
    return issues


def _collect_empty_min_height_div_issues(html: str) -> list[str]:
    issues: list[str] = []
    scan = _strip_scripts_and_styles(_body_markup(html))
    for match in _EMPTY_DIV.finditer(scan):
        attrs = match.group(1) or ""
        if "venue-map" in attrs.lower() or "map-stage" in attrs.lower():
            continue
        for hm in _MIN_H_ARBITRARY.finditer(attrs):
            px = int(hm.group(1))
            if px >= 560:
                issues.append(
                    f"Excess trailing whitespace: empty min-h-[{px}px] div (not map content) "
                    "inflates scroll — remove or shrink to fit real content."
                )
                return issues
    return issues


def _collect_last_section_padding_issues(html: str) -> list[str]:
    issues: list[str] = []
    body = _strip_scripts_and_styles(_body_markup(html))
    sections = list(_SECTION_OPEN.finditer(body))
    if not sections:
        return issues
    last = sections[-1]
    pb = _tailwind_padding_bottom_px(last.group(1) or "")
    if pb >= 128:
        issues.append(
            f"Excess trailing whitespace: last section uses large bottom padding (~{pb}px) — "
            "reduce pb-/py- utilities so the proposal ends near the footer/CTA."
        )
    return issues


def _collect_css_viewport_padding_issues(css: str) -> list[str]:
    issues: list[str] = []
    text = css or ""
    if not text.strip():
        return issues
    for block in re.findall(r"(?:html|body)\s*\{([^}]*)\}", text, re.I):
        if re.search(r"min-height\s*:\s*100vh", block, re.I):
            pb = re.search(r"padding-bottom\s*:\s*(\d+)", block, re.I)
            if pb and int(pb.group(1)) >= 96:
                issues.append(
                    "Excess trailing whitespace: body/html min-height:100vh with large "
                    "padding-bottom — shrink padding; do not combine full viewport height "
                    "with extra bottom pad."
                )
    return issues


def collect_trailing_whitespace_issues(html: str, css: str = "") -> list[str]:
    """Return human-readable blocking issues for large empty area below last content."""
    seen: set[str] = set()
    out: list[str] = []
    for item in (
        *_collect_stacked_viewport_height_issues(html),
        *_collect_trailing_tail_issues(html),
        *_collect_empty_min_height_div_issues(html),
        *_collect_last_section_padding_issues(html),
        *_collect_css_viewport_padding_issues(css),
    ):
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def preview_automation_trailing_gap_issue(report: dict | None) -> str | None:
    """When Live preview probes report a large docHeight vs content bottom gap."""
    if not report or report.get("error"):
        return None
    scroll = report.get("scroll") or {}
    gap = scroll.get("trailingGapPx")
    if gap is None:
        return None
    try:
        gap_px = int(gap)
    except (TypeError, ValueError):
        return None
    viewport = report.get("viewport") or {}
    vh = int(viewport.get("h") or 900)
    threshold = max(220, int(vh * 0.22))
    if gap_px < threshold:
        return None
    return (
        f"Excess trailing whitespace: live preview shows ~{gap_px}px empty scroll below "
        f"the last visible section (threshold {threshold}px) — remove trailing min-h-screen, "
        "spacer divs, and oversized pb-/py- on the final section."
    )
