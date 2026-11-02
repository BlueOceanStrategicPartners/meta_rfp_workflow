"""Structure-aware template indexing (CSS rules, HTML anchors, JS symbols).

Lightweight AST-style extraction without native parsers — tuned for proposal
html/css/js files. Follows progressive disclosure: list compact metadata,
read full symbol body only when editing.
"""
from __future__ import annotations

import hashlib
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal

from .template_workspace import TemplateFile, TemplateWorkspace, normalize_template_file_arg

_index_cache: dict[str, list["TemplateSymbol"]] = {}

SymbolKind = Literal["css_rule", "html_element", "js_symbol"]
KIND_FILTER = frozenset({"css_rule", "html_element", "js_symbol", "all"})


@dataclass(frozen=True)
class TemplateSymbol:
    id: str
    kind: SymbolKind
    name: str
    start_line: int
    end_line: int
    preview: str

    def to_dict(self, *, include_lines: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "preview": self.preview[:200],
        }
        if include_lines:
            out["start_line"] = self.start_line
            out["end_line"] = self.end_line
        return out


def _stable_id(file: str, kind: str, name: str, start_line: int) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)[:48] or "sym"
    return f"{file}:{start_line}:{kind}:{slug}"


def _line_number_at(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _extract_css_rules(css: str) -> list[TemplateSymbol]:
    symbols: list[TemplateSymbol] = []
    if not css.strip():
        return symbols

    depth = 0
    in_str: str | None = None
    rule_start = 0
    sel_start = 0
    i = 0
    n = len(css)

    while i < n:
        if in_str:
            if css[i] == "\\":
                i += 2
                continue
            if css[i] == in_str:
                in_str = None
            i += 1
            continue
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if css[i] in ("'", '"'):
            in_str = css[i]
            i += 1
            continue
        if css[i] == "{":
            if depth == 0:
                sel_start = rule_start
                selector = css[sel_start:i].strip()
                selector = " ".join(selector.split())
                if not selector:
                    selector = f"rule_at_{_line_number_at(css, i)}"
                body_open = i
                depth = 1
                i += 1
                inner_in_str: str | None = None
                while i < n and depth > 0:
                    if inner_in_str:
                        if css[i] == "\\":
                            i += 2
                            continue
                        if css[i] == inner_in_str:
                            inner_in_str = None
                        i += 1
                        continue
                    if css.startswith("/*", i):
                        end = css.find("*/", i + 2)
                        i = n if end < 0 else end + 2
                        continue
                    if css[i] in ("'", '"'):
                        inner_in_str = css[i]
                        i += 1
                        continue
                    if css[i] == "{":
                        depth += 1
                    elif css[i] == "}":
                        depth -= 1
                    i += 1
                start_line = _line_number_at(css, sel_start)
                end_line = _line_number_at(css, i)
                name = selector.split(",")[0].strip()[:120]
                preview = (selector + " { … }")[:160]
                sym_id = _stable_id("css", "css_rule", name, start_line)
                symbols.append(
                    TemplateSymbol(
                        id=sym_id,
                        kind="css_rule",
                        name=name,
                        start_line=start_line,
                        end_line=end_line,
                        preview=preview,
                    )
                )
                rule_start = i
                continue
            depth += 1
        elif css[i] == "}":
            if depth > 0:
                depth -= 1
            rule_start = i + 1
        i += 1
    return symbols


def _extract_html_elements(html: str) -> list[TemplateSymbol]:
    symbols: list[TemplateSymbol] = []
    lines = html.splitlines()
    seen: set[str] = set()
    id_re = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    class_re = re.compile(r'\bclass\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    tag_re = re.compile(r"<([a-zA-Z][\w-]*)\b")

    for line_no, line in enumerate(lines, start=1):
        if "<" not in line:
            continue
        tag_m = tag_re.search(line)
        tag = tag_m.group(1).lower() if tag_m else "element"
        names: list[str] = []
        id_m = id_re.search(line)
        if id_m:
            names.append(f"#{id_m.group(1)}")
        class_m = class_re.search(line)
        if class_m:
            for cls in class_m.group(1).split():
                if cls.strip():
                    names.append(f".{cls.strip()}")
        if not names:
            names.append(f"<{tag}>")
        for name in names[:4]:
            key = f"{line_no}:{name}"
            if key in seen:
                continue
            seen.add(key)
            sym_id = _stable_id("html", "html_element", name, line_no)
            symbols.append(
                TemplateSymbol(
                    id=sym_id,
                    kind="html_element",
                    name=name,
                    start_line=line_no,
                    end_line=min(len(lines), line_no + 2),
                    preview=line.strip()[:160],
                )
            )
    return symbols


_JS_PATTERNS = [
    re.compile(r"^\s*function\s+(\w+)\s*\(", re.MULTILINE),
    re.compile(r"^\s*(?:async\s+)?function\s+(\w+)\s*\(", re.MULTILINE),
    re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(", re.MULTILINE),
    re.compile(r"^\s*class\s+(\w+)\s*(?:extends|\{)", re.MULTILINE),
]


def _find_js_block_end(text: str, open_brace_index: int) -> int:
    depth = 0
    i = open_brace_index
    n = len(text)
    in_str: str | None = None
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            i += 1
            continue
        if text.startswith("//", i):
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _extract_js_symbols(js: str) -> list[TemplateSymbol]:
    symbols: list[TemplateSymbol] = []
    if not js.strip():
        return symbols
    seen_names: set[str] = set()
    for pattern in _JS_PATTERNS:
        for match in pattern.finditer(js):
            name = match.group(1)
            if name in seen_names:
                continue
            seen_names.add(name)
            start_line = _line_number_at(js, match.start())
            brace = js.find("{", match.end())
            if brace < 0:
                end_line = start_line
                preview = js[match.start() : match.end() + 40].replace("\n", " ")[:160]
            else:
                end_idx = _find_js_block_end(js, brace)
                end_line = _line_number_at(js, end_idx)
                preview = js[match.start() : min(match.start() + 120, end_idx)].replace("\n", " ")[:160]
            sym_id = _stable_id("js", "js_symbol", name, start_line)
            symbols.append(
                TemplateSymbol(
                    id=sym_id,
                    kind="js_symbol",
                    name=name,
                    start_line=start_line,
                    end_line=end_line,
                    preview=preview,
                )
            )
    return symbols


def _index_cache_key(workspace: TemplateWorkspace, file: TemplateFile) -> str:
    text = workspace.get_file(file)
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:20]
    return f"{file}:{digest}"


def clear_template_index_cache() -> None:
    _index_cache.clear()


def index_template_file(workspace: TemplateWorkspace, file: TemplateFile) -> list[TemplateSymbol]:
    key = _index_cache_key(workspace, file)
    cached = _index_cache.get(key)
    if cached is not None:
        return cached
    text = workspace.get_file(file)
    if file == "css":
        symbols = _extract_css_rules(text)
    elif file == "html":
        symbols = _extract_html_elements(text)
    elif file == "js":
        symbols = _extract_js_symbols(text)
    else:
        symbols = []
    _index_cache[key] = symbols
    return symbols


def index_all_template_files(workspace: TemplateWorkspace) -> list[TemplateSymbol]:
    out: list[TemplateSymbol] = []
    for file in ("css", "html", "js"):
        out.extend(index_template_file(workspace, file))
    return out


def find_symbol_by_id(workspace: TemplateWorkspace, symbol_id: str) -> TemplateSymbol | None:
    parts = symbol_id.split(":", 3)
    if len(parts) < 4:
        return None
    file_key = parts[0]
    try:
        start_line = int(parts[1])
    except ValueError:
        return None
    file: TemplateFile | None = None
    if file_key == "css":
        file = "css"
    elif file_key == "html":
        file = "html"
    elif file_key == "js":
        file = "js"
    if not file:
        return None
    for sym in index_template_file(workspace, file):
        if sym.id == symbol_id:
            return sym
        if sym.start_line == start_line and symbol_id.endswith(sym.name.replace(" ", "_")[:20]):
            return sym
    for sym in index_template_file(workspace, file):
        if sym.start_line == start_line:
            return sym
    return None


def read_symbol_body(workspace: TemplateWorkspace, symbol: TemplateSymbol) -> str:
    file: TemplateFile
    if symbol.id.startswith("css:"):
        file = "css"
    elif symbol.id.startswith("html:"):
        file = "html"
    elif symbol.id.startswith("js:"):
        file = "js"
    else:
        file = "html"
    return workspace.read_lines(file, symbol.start_line, symbol.end_line)


def compact_structure_outline(workspace: TemplateWorkspace, *, max_per_file: int = 14) -> str:
    """Token-budgeted repo-map style outline injected in the user anchor."""
    lines = ["TEMPLATE STRUCTURE OUTLINE (use list_template_symbols / read_template_symbol — avoid blind line reads):"]
    for file in ("css", "html", "js"):
        syms = index_template_file(workspace, file)[:max_per_file]
        if not syms:
            continue
        labels = [f"{s.name} (L{s.start_line}-{s.end_line})" for s in syms]
        extra = len(index_template_file(workspace, file)) - len(syms)
        suffix = f" (+{extra} more — list_template_symbols)" if extra > 0 else ""
        lines.append(f"- {file}: " + "; ".join(labels) + suffix)
    return "\n".join(lines)


def execute_list_template_symbols(
    workspace: TemplateWorkspace,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    try:
        file = normalize_template_file_arg(arguments.get("file"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    kind = str(arguments.get("kind") or "all").strip().lower()
    if kind not in KIND_FILTER:
        kind = "all"
    query = str(arguments.get("query") or "").strip().lower()
    max_items = min(40, max(1, int(arguments.get("max_items") or 24)))

    syms = index_template_file(workspace, file)  # type: ignore[arg-type]
    if kind != "all":
        syms = [s for s in syms if s.kind == kind]
    if query:
        syms = [
            s
            for s in syms
            if query in s.name.lower() or query in s.preview.lower()
        ]
    total = len(syms)
    syms = syms[:max_items]
    return {
        "ok": True,
        "file": file,
        "kind": kind,
        "symbols": [s.to_dict(include_lines=True) for s in syms],
        "total_matched": total,
        "shown": len(syms),
        "context_note": "Pass symbol id to read_template_symbol for full body, then replace_lines or replace_exact.",
    }


def execute_read_template_symbol(
    workspace: TemplateWorkspace,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    symbol_id = str(arguments.get("symbol_id") or arguments.get("id") or "").strip()
    if not symbol_id:
        return {"ok": False, "error": "symbol_id is required (from list_template_symbols)"}
    sym = find_symbol_by_id(workspace, symbol_id)
    if not sym:
        return {"ok": False, "error": f"symbol not found: {symbol_id}"}
    body = read_symbol_body(workspace, sym)
    return {
        "ok": True,
        "symbol": sym.to_dict(include_lines=True),
        "content": body,
        "edit_hint": f"replace_lines(file={symbol_id.split(':')[0]}, start_line={sym.start_line}, end_line={sym.end_line}, new_content=...)",
    }


def workspace_structure_fingerprint(workspace: TemplateWorkspace) -> str:
    blob = compact_structure_outline(workspace, max_per_file=8)
    return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()[:12]
