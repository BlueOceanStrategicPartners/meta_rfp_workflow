"""Fast line-attributed template lint (post-edit gate + lint_template tool)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .finalize_validation import collect_html_tag_balance_issues
from .services import deterministic_template_checks
from .tailwind_embedded_validation import collect_tailwind_and_embedded_style_issues
from .template_workspace import TemplateWorkspace

Severity = Literal["error", "warning"]
LintFile = Literal["html", "css", "js"]

_JS_LEAK_RE = re.compile(
    r"\b(document\.|window\.|addEventListener\s*\(|querySelector(?:All)?\s*\("
    r"|function\s+\w+\s*\(|=>\s*\{|const\s+\w+\s*=\s*(?:async\s*)?\(|let\s+\w+\s*=\s*function)",
    re.IGNORECASE,
)
_UNICODE_ESCAPE_RE = re.compile(r"\\[uU][0-9a-fA-F]{4,8}")
_SCRIPT_OPEN = re.compile(r"<script\b", re.IGNORECASE)
_SCRIPT_CLOSE = re.compile(r"</script\s*>", re.IGNORECASE)


@dataclass(frozen=True)
class LintDiagnostic:
    file: LintFile
    line: int
    end_line: int | None
    code: str
    message: str
    severity: Severity = "error"

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        if out.get("end_line") is None:
            out.pop("end_line", None)
        return out

    def format_line(self) -> str:
        if self.end_line and self.end_line != self.line:
            return f"{self.file}:{self.line}-{self.end_line}"
        return f"{self.file}:{self.line}"


def _diag_from_message(file: LintFile, message: str, *, code: str = "LINT") -> LintDiagnostic:
    line_m = re.search(r"line\s*~?\s*(\d+)", message, re.I)
    line = int(line_m.group(1)) if line_m else 1
    return LintDiagnostic(
        file=file,
        line=line,
        end_line=None,
        code=code,
        message=message,
        severity="error",
    )


def _find_line_containing(html: str, needle: str, *, start: int = 1) -> int:
    if not needle:
        return start
    for i, line in enumerate(html.splitlines(), start=1):
        if needle in line:
            return i
    return start


def lint_html_script_and_markup(html: str) -> list[LintDiagnostic]:
    """Detect unclosed <script> and JavaScript rendered as visible page text."""
    if not (html or "").strip():
        return [LintDiagnostic("html", 1, None, "EMPTY_HTML", "HTML body is empty.")]

    diags: list[LintDiagnostic] = []
    lines = html.splitlines()
    in_script = False
    script_start_line = 0
    open_scripts = 0

    for line_no, line in enumerate(lines, start=1):
        lower = line.lower()
        if not in_script:
            opens = len(_SCRIPT_OPEN.findall(line))
            closes = len(_SCRIPT_CLOSE.findall(line))
            if opens and not closes:
                in_script = True
                script_start_line = line_no
                open_scripts += opens
            elif opens and closes:
                continue
            else:
                if _JS_LEAK_RE.search(line) and "{{" not in line:
                    snippet = line.strip()[:80]
                    diags.append(
                        LintDiagnostic(
                            file="html",
                            line=line_no,
                            end_line=line_no,
                            code="JS_OUTSIDE_SCRIPT",
                            message=(
                                "JavaScript appears outside a <script> block — guests will see raw code on the page. "
                                f"Wrap in <script>…</script> or fix a missing </script>. Snippet: {snippet!r}"
                            ),
                        )
                    )
                if _UNICODE_ESCAPE_RE.search(line) and "<" in line:
                    diags.append(
                        LintDiagnostic(
                            file="html",
                            line=line_no,
                            end_line=line_no,
                            code="LITERAL_UNICODE_ESCAPE",
                            message=(
                                "Literal \\uXXXX escape sequences in HTML copy — use real characters (•) or entities."
                            ),
                            severity="warning",
                        )
                    )
        else:
            if _SCRIPT_CLOSE.search(line):
                in_script = False
                open_scripts = max(0, open_scripts - 1)
            elif _SCRIPT_OPEN.search(line):
                open_scripts += 1

    if in_script or open_scripts > 0:
        diags.append(
            LintDiagnostic(
                file="html",
                line=script_start_line or 1,
                end_line=None,
                code="UNCLOSED_SCRIPT",
                message=(
                    "Unclosed <script> tag — everything after this line may render as visible text. "
                    "Add </script> before the next HTML section."
                ),
            )
        )

    for msg in collect_html_tag_balance_issues(html):
        tag_m = re.search(r"Unbalanced <(\w+)>", msg, re.I)
        code = f"UNBALANCED_{tag_m.group(1).upper()}" if tag_m else "UNBALANCED_TAG"
        line = _find_line_containing(html, f"<{tag_m.group(1)}" if tag_m else "<", start=1)
        diags.append(
            LintDiagnostic(
                file="html",
                line=line,
                end_line=None,
                code=code,
                message=msg,
            )
        )

    return diags


def lint_template_workspace(workspace: TemplateWorkspace) -> dict[str, Any]:
    """Run deterministic checks with line-attributed diagnostics."""
    html = workspace.html_markup or ""
    css = workspace.css_stylesheet or ""
    js = workspace.js_script or ""

    diagnostics: list[LintDiagnostic] = []
    diagnostics.extend(lint_html_script_and_markup(html))

    for msg in collect_tailwind_and_embedded_style_issues(html, css, js):
        needle = msg.split("(")[0][-40:].strip() if "(" in msg else msg[:40]
        line = _find_line_containing(html, ".hero-bg") if ".hero" in msg.lower() else _find_line_containing(html, "<style")
        if "plain text" in msg.lower():
            line = _find_line_containing(html, "{")
        diagnostics.append(
            LintDiagnostic(
                file="html",
                line=line,
                end_line=None,
                code="TAILWIND_OR_STYLE",
                message=msg,
            )
        )

    for msg in deterministic_template_checks(html, css, js):
        if any(d.message == msg for d in diagnostics):
            continue
        file: LintFile = "html"
        if "css" in msg.lower() and "html" not in msg.lower():
            file = "css"
        if "js" in msg.lower() or "script" in msg.lower():
            file = "html"
        diagnostics.append(_diag_from_message(file, msg, code="TEMPLATE_RULE"))

    errors = [d for d in diagnostics if d.severity == "error"]
    valid = len(errors) == 0
    return {
        "ok": True,
        "valid": valid,
        "diagnostics": [d.to_dict() for d in diagnostics[:40]],
        "issues": [f"{d.format_line()} [{d.code}] {d.message}" for d in diagnostics[:25]],
        "summary": "Lint passed." if valid else f"{len(errors)} error(s) — fix before next plan step.",
        "agent_workflow": (
            "Fix each diagnostic at the given file:line (read_template_lines or read_template_symbol), "
            "then mutate. Execution plan / todos do not advance until post-edit lint is clean."
        ),
    }


def run_post_edit_validation(
    workspace: TemplateWorkspace,
    *,
    message: str = "",
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Combine deterministic gate + line lint for automatic post-mutate checks."""
    from .designer_validation import validate_template_deterministic_gate

    gate = validate_template_deterministic_gate(
        html=workspace.html_markup,
        css=workspace.css_stylesheet,
        js=workspace.js_script,
        message=message,
        history=history,
    )
    lint = lint_template_workspace(workspace)

    seen: set[str] = set()
    issues: list[str] = []
    for item in list(gate.get("issues") or []) + list(lint.get("issues") or []):
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            issues.append(text)

    valid = bool(gate.get("valid")) and bool(lint.get("valid"))
    return {
        "valid": valid,
        "issues": issues,
        "diagnostics": lint.get("diagnostics") or [],
        "summary": lint.get("summary") if not valid else str(gate.get("summary") or "Post-edit checks passed."),
        "deterministic_valid": bool(gate.get("valid")),
        "lint_valid": bool(lint.get("valid")),
    }


def format_diagnostics_control_block(payload: dict[str, Any], *, max_items: int = 12) -> str:
    lines = [
        "CONTROL: Post-edit lint failed — fix these before the execution plan advances "
        "(read file:line → replace_lines / replace_exact):"
    ]
    diags = payload.get("diagnostics") or []
    if diags:
        for d in diags[:max_items]:
            if not isinstance(d, dict):
                continue
            loc = f"{d.get('file', 'html')}:{d.get('line', '?')}"
            code = d.get("code") or "LINT"
            msg = str(d.get("message") or "")[:220]
            lines.append(f"- {loc} [{code}] {msg}")
    else:
        for item in (payload.get("issues") or [])[:max_items]:
            lines.append(f"- {item}")
    return "\n".join(lines)
