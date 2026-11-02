"""Chat-turn template validation (deterministic + Muse) — shared by LangGraph validator node."""
from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.designer_studio.services import compile_template, deterministic_template_checks
from apps.rfp_debate.meta_client import MetaModelClient

from .template_alignment import collect_alignment_issues

VALIDATION_SYSTEM_PROMPT = (
    "You validate compiled hospitality proposal HTML/CSS/JS templates against the user's brief. "
    "Return JSON only: valid (boolean), issues (string array), summary (string). "
    "Check media embeds, nav/icon markup, CTA visibility (accept button must not use display:none), "
    "responsive layout, JS safety, and that visible dates match the requested locale/format "
    "(U.S. MM/DD/YYYY vs ISO) when the brief mentions it. "
    "Template HTML uses {{binding_tokens}} in source — that is correct; do not flag tokens as "
    "'unresolved' or 'not verifiable' in the template source. "
    "CSS/HTML/JS in this prompt may be truncated for length — do not report prompt truncation "
    "as a template defect."
)

MUSE_SPURIOUS_ISSUE_PHRASES = (
    "unresolved token",
    "compilation is incomplete",
    "no rendered dates to validate",
    "no media/map embed",
    "no media embed",
    "no map embed",
    "compiled preview truncated",
    "preview truncated",
    "css ends mid",
    "placeholders not verifiable",
    "placeholder tokens",
    "no resolved values visible",
    "cannot be verified",
    "body html not shown",
    "not verifiable in compiled",
)


def filter_muse_validation_issues(issues: list[str]) -> list[str]:
    filtered: list[str] = []
    for item in issues:
        lower = item.lower()
        if any(p in lower for p in MUSE_SPURIOUS_ISSUE_PHRASES):
            continue
        filtered.append(item)
    return filtered


def collect_deterministic_chat_issues(
    *,
    message: str,
    history: list[dict[str, str]] | None,
    html: str,
    css: str,
    js: str,
) -> list[str]:
    issues = deterministic_template_checks(html, css, js)
    issues.extend(
        collect_alignment_issues(message=message, history=history, html=html, css=css)
    )
    seen: set[str] = set()
    unique: list[str] = []
    for item in issues:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def muse_validate_chat_layout(
    *,
    html_markup: str,
    css_stylesheet: str,
    js_script: str = "",
    user_brief: str = "",
    client: MetaModelClient | None = None,
    include_deterministic: bool = True,
) -> dict[str, Any]:
    """Muse layout review for post-executor self-check (fixture_kind=designer_validate)."""
    deterministic_issues: list[str] = []
    if include_deterministic:
        deterministic_issues = collect_deterministic_chat_issues(
            message=user_brief,
            history=None,
            html=html_markup,
            css=css_stylesheet,
            js=js_script,
        )
    compiled = compile_template(html_markup, css_stylesheet, js_script=js_script)
    css_block = css_stylesheet[:24000]
    if len(css_stylesheet) > len(css_block):
        css_block += f"\n\n… ({len(css_stylesheet) - len(css_block)} more CSS chars omitted from review prompt)"
    brief_block = f"User brief:\n{user_brief[:4000]}\n\n" if user_brief else ""
    messages = [
        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{brief_block}"
                f"Template HTML (tokens):\n{html_markup[:10000]}\n\n"
                f"CSS:\n{css_block}\n\n"
                f"JS:\n{js_script[:6000]}\n\n"
                f"Compiled preview:\n{compiled[:10000]}"
            ),
        },
    ]
    llm = client or MetaModelClient()
    raw = llm.complete_json_messages(
        model_id=settings.META_MODEL_SPARK,
        messages=messages,
        fixture_kind="designer_validate",
    )
    muse_issues = filter_muse_validation_issues(
        [str(i) for i in (raw.get("issues") or []) if i]
    )
    all_issues = deterministic_issues + muse_issues
    valid = not deterministic_issues and not muse_issues
    return {
        "valid": valid,
        "issues": all_issues,
        "summary": str(
            raw.get("summary")
            or ("Template passes validation." if valid else "Template needs fixes.")
        ),
        "model_id": settings.META_MODEL_SPARK,
        "deterministic_issues": deterministic_issues,
        "muse_issues": muse_issues,
    }


def validate_template_deterministic_gate(
    *,
    html: str,
    css: str,
    js: str = "",
    message: str = "",
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Fast post-edit gate (no Muse) — keeps live progress responsive during tool loops."""
    issues = collect_deterministic_chat_issues(
        message=message,
        history=history,
        html=html,
        css=css,
        js=js,
    )
    valid = not issues
    return {
        "valid": valid,
        "issues": issues,
        "summary": "Quick checks passed." if valid else "; ".join(issues[:6]),
        "deterministic_issues": issues,
        "muse_issues": [],
    }


def validate_template_like_button(
    *,
    html: str,
    css: str,
    js: str = "",
    message: str = "",
    history: list[dict[str, str]] | None = None,
    client: MetaModelClient | None = None,
) -> dict[str, Any]:
    """Same validation path as POST /api/designer/validate/ (Check template button)."""
    _ = history
    return muse_validate_chat_layout(
        html_markup=html,
        css_stylesheet=css,
        js_script=js,
        user_brief=message,
        client=client,
        include_deterministic=True,
    )


def gather_chat_validation_issues(
    *,
    message: str,
    history: list[dict[str, str]],
    result: dict[str, Any],
    client: MetaModelClient | None = None,
) -> list[str]:
    """Blocking issues after executor — deterministic only by default (no Muse repair loop)."""
    _ = client
    deterministic_only = getattr(settings, "DESIGNER_VALIDATOR_DETERMINISTIC_ONLY", True)
    if deterministic_only:
        review = validate_template_deterministic_gate(
            html=result.get("html_markup") or "",
            css=result.get("css_stylesheet") or "",
            js=result.get("js_script") or "",
            message=message,
            history=history,
        )
        if review.get("valid"):
            return []
        return list(review.get("issues") or [])

    review = validate_template_like_button(
        html=result.get("html_markup") or "",
        css=result.get("css_stylesheet") or "",
        js=result.get("js_script") or "",
        message=message,
        history=history,
        client=client,
    )
    if review.get("valid"):
        return []
    return list(review.get("issues") or [])


def should_skip_post_executor_validation(result: dict[str, Any]) -> bool:
    if result.get("model_api_error"):
        return True
    if result.get("tool_loop_exhausted") and not (result.get("tool_trace") or []):
        return True
    return False
