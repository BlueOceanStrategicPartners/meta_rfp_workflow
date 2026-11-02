"""Agent workflow modes and pool-calling playbooks (prompt + context engineering)."""
from __future__ import annotations

from typing import Literal

from .designer_map_intent import message_has_map_intent
from .template_workspace import TemplateWorkspace

AgentWorkflowMode = Literal["greenfield_create", "update_existing", "fix_validation"]


def resolve_agent_workflow_mode(
    workspace: TemplateWorkspace,
    message: str,
    *,
    repair_mode: bool = False,
) -> AgentWorkflowMode:
    from .tool_loop_context import is_greenfield_template

    if repair_mode:
        return "fix_validation"
    if is_greenfield_template(workspace):
        return "greenfield_create"
    return "update_existing"


def _map_tools_prefix(message: str, workspace: TemplateWorkspace) -> list[str]:
    if not (message_has_map_intent(message) or "venue-map-proposal" in (workspace.html_markup or "")):
        return []
    return [
        "Map slice (only if user wants a floorplan / interactive map):",
        "  • get_map_knowledge(topic=checklist) + get_map_reference_code(part=structure)",
        "  • Then edit the .venue-map-proposal section via section pool (not get_template_overview).",
    ]


def build_pool_calling_playbook(
    mode: AgentWorkflowMode,
    *,
    message: str,
    workspace: TemplateWorkspace,
) -> str:
    """Concrete follow-up steps injected into every tool-loop user anchor."""
    user_snippet = (message or "").strip()[:500]
    lines = [
        f"AGENT MODE: {mode.replace('_', ' ').upper()}",
        "POOL-CALLING (mandatory — minimizes tool spam):",
        "Use the PROPOSAL SECTION POOL + semantic list_template_symbols(query=…) to pick targets.",
        "One section = full HTML + Tailwind + inline JS. Patch with read_template_symbol → replace_lines.",
        "",
        "TOOLS TO SKIP unless a patch failed or pool is empty:",
        "  • get_template_overview (snapshot below is authoritative)",
        "  • list_template_symbols / search_template (hybrid) → read_template_symbol — not read_template_lines for whole sections",
        "  • Repeating list_template_symbols with the same query after a successful read",
        "  • validate_template more than once per revision (post-edit lint runs automatically after edits)",
        "",
    ]

    if mode == "greenfield_create":
        lines.extend(
            [
                "FOLLOW-UP STEPS — NEW PROPOSAL:",
                "Turn 1 (mutate, no read-only prelude):",
                "  • append_template(file=html) — one Tailwind single-file doc with ALL mandatory {{placeholders}},",
                "    multiple <section id=\"…\"> blocks (hero, room block, meeting, pricing, CTA), bottom <script>.",
            ]
        )
        lines.extend(_map_tools_prefix(message, workspace))
        lines.extend(
            [
                "Turn 2+ (only if user asked for more polish or map):",
                "  • list_template_symbols(file=html, kind=proposal_section, query=<user topic>)",
                "  • read_template_symbol(top section id) + replace_lines in the SAME tools batch",
                "Finish: kind=finish when placeholders present and request satisfied — do not overview-loop.",
            ]
        )
    elif mode == "update_existing":
        lines.extend(
            [
                "FOLLOW-UP STEPS — UPDATE / FIX EXISTING PROPOSAL:",
                "Turn 1 (prefer one batch):",
                f'  • list_template_symbols(file=html, kind=proposal_section, query="{user_snippet or "user request"}")',
                "  • read_template_symbol(symbol_id) for the top-ranked section only",
                "  • replace_lines on that section’s line range (same batch)",
            ]
        )
        lines.extend(_map_tools_prefix(message, workspace))
        lines.extend(
            [
                "Turn 2+ (other sections or follow-up tweaks):",
                "  • New query string per section — list → read → replace_lines; never re-list the same query",
                "  • replace_exact only for tiny token/string swaps inside a section you already read",
                "If pool returns zero sections: append_template to add a <section> block, then continue pool edits.",
                "Finish: kind=finish after edits; optional single validate_template only if unsure.",
            ]
        )
    else:
        lines.extend(
            [
                "FOLLOW-UP STEPS — VALIDATION REPAIR:",
                "Turn 1: validate_template(scope=systematic) — read issues + pool_repair_hints.",
                "  • list_template_symbols → read_template_symbol → replace_lines per hint.",
                "Turn 2: validate_template again; finish only when valid=true (finalize gate matches).",
            ]
        )

    return "\n".join(lines)


def build_designer_request_footer(
    mode: AgentWorkflowMode,
    *,
    continuation: bool,
    original_request: str,
) -> str:
    if continuation:
        return (
            "Designer request (continuation):\n"
            "Execute the FOLLOW-UP STEPS for your AGENT MODE using pool-calling only.\n"
            f"Original brief:\n{original_request[:2000]}"
        )
    verb = {
        "greenfield_create": "Create the proposal using GREENFIELD steps only.",
        "update_existing": "Update the existing proposal using UPDATE steps only.",
        "fix_validation": "Fix validation issues using REPAIR steps only.",
    }[mode]
    return (
        f"Designer request:\n{original_request[:4000]}\n\n"
        f"{verb} Do not call get_template_overview. "
        "Batch list_template_symbols (semantic query) + read_template_symbol + replace_lines per turn."
    )
