"""Structured tool-call memory for designer agent loops (context graph-lite)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .template_agent_tools import execute_template_tool, human_tool_label
from .template_workspace import TemplateWorkspace
from .tool_loop_context import shrink_tool_result_for_model

READ_ONLY_TOOLS = frozenset(
    {
        "get_template_overview",
        "list_template_symbols",
        "read_template_symbol",
        "read_template_lines",
        "search_template",
        "validate_template",
        "lint_template",
        "get_map_knowledge",
        "get_map_reference_code",
    }
)
MUTATING_TOOLS = frozenset({"replace_exact", "replace_lines", "append_template"})

MEMORY_MESSAGE_PREFIX = "TOOL SESSION MEMORY (authoritative graph — do not repeat entries marked DONE at same template revision):"


def workspace_fingerprint(workspace: TemplateWorkspace) -> str:
    blob = "\n".join(
        [
            workspace.html_markup or "",
            workspace.css_stylesheet or "",
            workspace.js_script or "",
        ]
    )
    return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()[:16]


def _args_key(arguments: dict[str, Any]) -> str:
    try:
        return json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False)
    except TypeError:
        return str(arguments)


def _summarize_result(tool: str, result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return f"failed: {str(result.get('error') or 'error')[:120]}"
    if tool in MUTATING_TOOLS:
        if result.get("replacements"):
            return f"applied {result['replacements']} replacement(s)"
        if result.get("start_line") is not None:
            return f"updated lines {result.get('start_line')}-{result.get('end_line')}"
        return "file updated"
    if tool == "search_template":
        mode = str(result.get("mode") or "hybrid")
        n = len(result.get("hits") or [])
        if mode == "hybrid" and n:
            top = (result.get("hits") or [{}])[0]
            name = str(top.get("name") or "match")
            return f"{n} structure match(es) — top: {name[:48]}"
        return f"{n} hit(s) on {result.get('file')}/{result.get('query')!r}"
    if tool == "read_template_lines":
        return f"read {result.get('file')} lines {result.get('start_line')}-{result.get('end_line')}"
    if tool == "lint_template":
        if result.get("valid"):
            return "lint passed"
        n = len(result.get("diagnostics") or result.get("issues") or [])
        return f"{n} lint issue(s)"
    if tool == "validate_template":
        if result.get("valid"):
            return "valid"
        issues = result.get("issues") or []
        return f"{len(issues)} issue(s)"
    if tool == "get_template_overview":
        return (
            f"html {result.get('html_lines')} lines, css {result.get('css_lines')} lines, "
            f"js {result.get('js_lines')} lines"
        )
    if tool == "list_template_symbols":
        return f"{result.get('shown')}/{result.get('total_matched')} symbol(s) in {result.get('file')}"
    if tool == "read_template_symbol":
        sym = result.get("symbol") or {}
        return f"symbol {sym.get('name')} lines {sym.get('start_line')}-{sym.get('end_line')}"
    if tool == "get_map_knowledge":
        return f"topic {result.get('topic') or 'overview'}"
    if tool == "get_map_reference_code":
        return f"part {result.get('part') or 'structure'}"
    return "ok"


@dataclass
class ToolSessionMemory:
    """Tracks tools, edits, and caches read-only results per workspace revision."""

    workspace_fp: str = ""
    entries: list[dict[str, Any]] = field(default_factory=list)
    cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    identical_cached_turns: int = 0
    last_batch_signature: str = ""
    continuation_mode: bool = False

    def bind_workspace(self, workspace: TemplateWorkspace) -> None:
        self.workspace_fp = workspace_fingerprint(workspace)

    @classmethod
    def from_action_state(cls, history: list[dict]) -> ToolSessionMemory:
        for turn in reversed(history or []):
            if turn.get("role") != "assistant":
                continue
            st = turn.get("action_state")
            if not isinstance(st, dict):
                continue
            graph = st.get("tool_session_graph")
            if isinstance(graph, dict):
                return cls.from_dict(graph)
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolSessionMemory:
        # Read-only cache is in-process only; restoring it after Continue caused
        # instant cached overview loops with no template mutations.
        mem = cls(
            workspace_fp=str(data.get("workspace_fp") or ""),
            entries=list(data.get("entries") or [])[-80:],
            cache={},
        )
        return mem

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_fp": self.workspace_fp,
            "entries": self.entries[-80:],
        }

    def prepare_continuation(self, workspace: TemplateWorkspace) -> None:
        """Fresh continuation: keep edit history, drop read cache and stuck counters."""
        self.continuation_mode = True
        self.cache.clear()
        self.identical_cached_turns = 0
        self.last_batch_signature = ""
        self.bind_workspace(workspace)

    def reset_stuck_tracking(self) -> None:
        self.identical_cached_turns = 0
        self.last_batch_signature = ""

    def _cache_key(self, tool: str, arguments: dict[str, Any]) -> str:
        return f"{self.workspace_fp}|{tool}|{_args_key(arguments)}"

    def is_read_only(self, tool: str) -> bool:
        return tool in READ_ONLY_TOOLS

    def lookup_cached(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if tool not in READ_ONLY_TOOLS:
            return None
        hit = self.cache.get(self._cache_key(tool, arguments))
        return dict(hit) if isinstance(hit, dict) else None

    def record(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        from_cache: bool,
    ) -> None:
        mutated = tool in MUTATING_TOOLS and bool(result.get("ok"))
        summary = _summarize_result(tool, result)
        label = human_tool_label(tool)
        entry = {
            "tool": tool,
            "args": arguments,
            "ok": bool(result.get("ok")),
            "mutated": mutated,
            "from_cache": from_cache,
            "summary": summary,
            "label": label,
            "workspace_fp": self.workspace_fp,
        }
        self.entries.append(entry)
        if len(self.entries) > 120:
            self.entries = self.entries[-120:]

        if tool in READ_ONLY_TOOLS and result.get("ok") and not from_cache:
            self.cache[self._cache_key(tool, arguments)] = shrink_tool_result_for_model(result)

    def execute(
        self,
        workspace: TemplateWorkspace,
        tool: str,
        arguments: dict[str, Any],
        *,
        user_brief: str = "",
    ) -> tuple[dict[str, Any], bool]:
        """Run tool with session cache for read-only calls."""
        fp = workspace_fingerprint(workspace)
        if fp != self.workspace_fp:
            self.workspace_fp = fp
            self.cache.clear()
            self.identical_cached_turns = 0
            self.last_batch_signature = ""

        if self.continuation_mode and tool == "get_template_overview":
            blocked = {
                "ok": False,
                "error": (
                    "get_template_overview is blocked during Continue — use CURRENT TEMPLATE SNAPSHOT "
                    "and a tools batch with search/read plus replace_exact or replace_lines."
                ),
                "control": "use_edit_tools",
            }
            self.record(tool=tool, arguments=arguments, result=blocked, from_cache=False)
            return blocked, False

        cached = self.lookup_cached(tool, arguments)
        if cached is not None:
            out = dict(cached)
            out["session_note"] = (
                "Returned from session memory (already run at this template revision)."
            )
            self.record(tool=tool, arguments=arguments, result=out, from_cache=True)
            return out, True

        result = execute_template_tool(workspace, tool, arguments, user_brief=user_brief)
        self.record(tool=tool, arguments=arguments, result=result, from_cache=False)
        return result, False

    def note_batch_outcome(self, batch_signature: str, *, all_from_cache: bool, any_mutated: bool) -> None:
        if any_mutated:
            self.identical_cached_turns = 0
            self.last_batch_signature = ""
            return
        if all_from_cache and batch_signature == self.last_batch_signature:
            self.identical_cached_turns += 1
        elif all_from_cache:
            self.identical_cached_turns = 1
            self.last_batch_signature = batch_signature
        else:
            self.identical_cached_turns = 0
            self.last_batch_signature = ""

    def stuck_on_cached_repeats(self, threshold: int) -> bool:
        return self.identical_cached_turns >= threshold

    def format_for_prompt(self, *, max_edits: int = 12, max_reads: int = 16) -> str:
        edits: list[str] = []
        reads: list[str] = []
        blocked: list[str] = []
        seen_block: set[str] = set()

        for entry in reversed(self.entries):
            if entry.get("workspace_fp") and entry.get("workspace_fp") != self.workspace_fp:
                continue
            tool = str(entry.get("tool") or "")
            args = entry.get("args") or {}
            args_short = _args_key(args)[:160]
            line = f"- {entry.get('label') or tool}: {entry.get('summary')} (args {args_short})"
            if entry.get("from_cache"):
                line += " [cached replay]"

            if entry.get("mutated") and len(edits) < max_edits:
                edits.append(line)
            elif tool in READ_ONLY_TOOLS and entry.get("ok") and len(reads) < max_reads:
                reads.append(line)

            block_key = f"{tool}|{args_short}"
            if (
                tool in READ_ONLY_TOOLS
                and entry.get("ok")
                and block_key not in seen_block
                and len(blocked) < 20
            ):
                seen_block.add(block_key)
                blocked.append(f"- DONE (skip): {tool} with same arguments")

        parts = [MEMORY_MESSAGE_PREFIX, f"Template revision: {self.workspace_fp or 'unknown'}"]
        if edits:
            parts.append("Edits applied this session:")
            parts.extend(edits[:max_edits])
        if reads:
            parts.append("Investigation already completed:")
            parts.extend(reads[:max_reads])
        if blocked and not self.continuation_mode:
            parts.append("Do NOT repeat these read-only calls (use edit tools next):")
            parts.extend(blocked[:20])
        elif blocked and self.continuation_mode:
            parts.append(
                "Prior investigation is recorded — do NOT call get_template_overview again. "
                "Use NEW search/read queries only if needed, always in the same batch as replace_exact/replace_lines."
            )
        if not edits and not reads:
            parts.append("- No tools recorded yet; batch search + read + replace toward the user request.")
        if self.continuation_mode:
            parts.append(
                "CONTINUATION (mandatory): Your next model turn MUST include at least one of "
                "replace_exact, replace_lines, or append_template. Read-only-only batches are rejected."
            )
        else:
            parts.append(
                "Next: use multi-tool batches with replace_exact/replace_lines on css/html for remaining issues — "
                "not another overview-only pass."
            )
        return "\n".join(parts)


def batch_is_read_only_only(tool_batch: list[dict[str, Any]]) -> bool:
    if not tool_batch:
        return False
    for spec in tool_batch:
        tool = str(spec.get("tool") or "").strip()
        if tool not in READ_ONLY_TOOLS:
            return False
    return True


def inject_session_memory_message(messages: list[dict[str, str]], memory: ToolSessionMemory) -> None:
    """Keep a single rolling memory message in the chat for the model."""
    messages[:] = [m for m in messages if not str(m.get("content", "")).startswith(MEMORY_MESSAGE_PREFIX)]
    messages.append({"role": "user", "content": memory.format_for_prompt()[:14000]})
