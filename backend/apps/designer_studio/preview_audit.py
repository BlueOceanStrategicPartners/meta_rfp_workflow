"""Deterministic Live preview audit (structure/DOM hints — complements Muse validation)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .layout_spacing_validation import collect_trailing_whitespace_issues
from .services import compile_template


@dataclass
class PreviewFinding:
    code: str
    message: str
    severity: str = "warning"


def audit_compiled_proposal_preview(html: str, css: str, js: str = "") -> list[PreviewFinding]:
    findings: list[PreviewFinding] = []
    compiled = compile_template(html or "", css or "", js_script=js or "")
    combined = (html or "") + (css or "") + (js or "") + compiled

    if "{{selected_map_svg}}" in (html or "") and "venue-map" not in combined.lower():
        findings.append(
            PreviewFinding(
                "map_slot_empty",
                "Proposal has {{selected_map_svg}} but no venue-map section styles/markup were detected.",
            )
        )

    if re.search(r"map-popup", combined, re.I):
        if not re.search(r"map-popup[^>]*hidden|classList\.add\s*\(\s*['\"]hidden['\"]", combined):
            if re.search(r"map-popup[^>]*(?!hidden)[^>]*>", html or "", re.I):
                findings.append(
                    PreviewFinding(
                        "map_popup_visible",
                        "Map popup markup may render open on load — popups should start with class hidden until a zone is clicked.",
                        severity="error",
                    )
                )
        if re.search(r"\.map-popup\s*\{[^}]*position\s*:\s*fixed[^}]*inset\s*:\s*0", css or "", re.I):
            findings.append(
                PreviewFinding(
                    "map_popup_fullscreen",
                    "Map popup CSS uses position:fixed inset:0 — this covers the whole proposal; use a panel anchored to the map or inset:20% instead.",
                    severity="error",
                )
            )
        if re.search(r"showPopup\s*\(", js or "") and not re.search(
            r"closePopup|classList\.add\s*\(\s*['\"]hidden['\"]", js or ""
        ):
            findings.append(
                PreviewFinding(
                    "map_popup_no_close",
                    "Map JS opens popups but has no close/hide handler — add close control that adds hidden class.",
                    severity="warning",
                )
            )

    if re.search(r"×\s*close|>\s*close\s*<", compiled, re.I) and "map-popup" in combined.lower():
        findings.append(
            PreviewFinding(
                "map_close_chrome",
                "Large Close control on the map may block the floorplan — use a small popup dismiss, not a full-map overlay.",
                severity="warning",
            )
        )

    if re.search(r"\.proposal-cta[^}]*display\s*:\s*none", css or "", re.I):
        findings.append(
            PreviewFinding(
                "cta_hidden",
                "Accept CTA may be hidden by CSS at default breakpoints.",
                severity="error",
            )
        )

    hero_markers = ("hero", "proposal-hero", "<h1", "main")
    if not any(m in (html or "").lower() for m in hero_markers):
        findings.append(
            PreviewFinding(
                "proposal_structure",
                "No clear hero/main section detected — proposal content may not render above the map.",
                severity="warning",
            )
        )

    for message in collect_trailing_whitespace_issues(html or "", css or ""):
        findings.append(
            PreviewFinding(
                "trailing_whitespace",
                message,
                severity="error",
            )
        )

    return findings


def format_preview_audit_for_agent(findings: list[PreviewFinding]) -> str:
    if not findings:
        return ""
    lines = ["LIVE PREVIEW AUDIT (deterministic — fix before replying):"]
    for f in findings:
        lines.append(f"- [{f.severity}] {f.code}: {f.message}")
    lines.append(
        "Treat these as bugs to fix in html/css/js. Map popups must stay hidden until zone click; "
        "proposal hero/CTA must remain visible. Remove trailing dead space — the page should end "
        "at the footer or last section without a large empty band below."
    )
    return "\n".join(lines)
