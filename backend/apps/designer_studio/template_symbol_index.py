"""Structure-aware template indexing (CSS rules, HTML anchors, JS symbols).

Lightweight AST-style extraction without native parsers — tuned for proposal
html/css/js files. Follows progressive disclosure: list compact metadata,
read full symbol body only when editing.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal

from .template_workspace import TemplateFile, TemplateWorkspace, normalize_template_file_arg

from .agent_rules import hybrid_query_document_score

_index_cache: dict[str, list["TemplateSymbol"]] = {}

SymbolKind = Literal["css_rule", "html_element", "js_symbol", "proposal_section"]
KIND_FILTER = frozenset({"css_rule", "html_element", "js_symbol", "proposal_section", "all"})


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


_SECTION_TAGS = ("section", "header", "footer", "main", "article")
_OPEN_TAG = re.compile(
    r"<(section|header|footer|main|article)(\s[^>]*)?>",
    re.IGNORECASE,
)


def _section_label(tag: str, attrs: str, inner: str) -> str:
    id_m = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
    if id_m:
        return f"{tag}#{id_m.group(1)}"
    aria_m = re.search(r'aria-label\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
    if aria_m:
        return f"{tag}:{aria_m.group(1).strip()[:48]}"
    class_m = re.search(r'\bclass\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
    if class_m:
        tokens = [t for t in class_m.group(1).split() if t.strip()]
        if tokens:
            return f"{tag}.{tokens[0]}"
    heading = re.search(r"<h[1-3][^>]*>([^<]{1,80})", inner, re.IGNORECASE)
    if heading:
        title = " ".join(heading.group(1).split())[:48]
        if title:
            return f"{tag}:{title}"
    return f"<{tag}>"


def _find_balanced_close(html: str, tag: str, open_end: int) -> int | None:
    """Return index after closing tag, or None if unbalanced."""
    tag_l = tag.lower()
    open_re = re.compile(rf"<{tag_l}(\s[^>]*)?>", re.IGNORECASE)
    close_re = re.compile(rf"</{tag_l}\s*>", re.IGNORECASE)
    depth = 1
    pos = open_end
    n = len(html)
    while depth > 0 and pos < n:
        close_m = close_re.search(html, pos)
        if not close_m:
            return None
        open_m = open_re.search(html, pos, close_m.start())
        if open_m:
            depth += 1
            pos = open_m.end()
            continue
        depth -= 1
        pos = close_m.end()
        if depth == 0:
            return pos
    return None


def _extract_proposal_sections(html: str) -> list[TemplateSymbol]:
    """Top-level proposal blocks (section/header/main/footer/article) including inline Tailwind + script."""
    symbols: list[TemplateSymbol] = []
    if not html.strip():
        return symbols
    occupied: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(not (end <= a or start >= b) for a, b in occupied)

    for m in _OPEN_TAG.finditer(html):
        start_idx = m.start()
        if overlaps(start_idx, start_idx + 1):
            continue
        tag = m.group(1).lower()
        attrs = m.group(2) or ""
        close_end = _find_balanced_close(html, tag, m.end())
        if close_end is None:
            continue
        end_idx = close_end
        if overlaps(start_idx, end_idx):
            continue
        occupied.append((start_idx, end_idx))
        start_line = _line_number_at(html, start_idx)
        end_line = _line_number_at(html, end_idx)
        inner = html[m.end() : close_end]
        name = _section_label(tag, attrs, inner)
        preview = html[start_idx : min(start_idx + 200, end_idx)].replace("\n", " ").strip()
        sym_id = _stable_id("html", "proposal_section", name, start_line)
        symbols.append(
            TemplateSymbol(
                id=sym_id,
                kind="proposal_section",
                name=name,
                start_line=start_line,
                end_line=end_line,
                preview=preview,
            )
        )
    symbols.sort(key=lambda s: s.start_line)
    return symbols


def _line_in_section_ranges(line_no: int, sections: list[TemplateSymbol]) -> bool:
    return any(s.start_line <= line_no <= s.end_line for s in sections)


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


def _extract_inline_style_blocks(html: str) -> list[TemplateSymbol]:
    """Tailwind single-file: embedded <style> blocks as css_rule symbols."""
    symbols: list[TemplateSymbol] = []
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", html, re.IGNORECASE | re.DOTALL):
        inner = m.group(1)
        if not inner.strip():
            continue
        start_line = _line_number_at(html, m.start())
        end_line = _line_number_at(html, m.end())
        preview = inner.strip().replace("\n", " ")[:160]
        name = f"inline-style@L{start_line}"
        sym_id = _stable_id("html", "css_rule", name, start_line)
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
    return symbols


def _extract_inline_script_blocks(html: str) -> list[TemplateSymbol]:
    """Non-JSON <script> blocks in single-file proposals."""
    symbols: list[TemplateSymbol] = []
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, re.IGNORECASE | re.DOTALL):
        attrs = m.group(1) or ""
        if re.search(r'type\s*=\s*["\']application/json["\']', attrs, re.IGNORECASE):
            continue
        inner = m.group(2)
        if not inner.strip():
            continue
        start_line = _line_number_at(html, m.start())
        end_line = _line_number_at(html, m.end())
        preview = inner.strip().replace("\n", " ")[:160]
        id_m = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        name = f"script#{id_m.group(1)}" if id_m else f"inline-script@L{start_line}"
        sym_id = _stable_id("html", "js_symbol", name, start_line)
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


def _build_symbol_search_document(workspace: TemplateWorkspace, symbol: TemplateSymbol) -> str:
    """Rich retrieval text: name, preview, placeholders, Tailwind classes, binding hooks."""
    parts = [symbol.kind, symbol.name, symbol.preview]
    try:
        body = read_symbol_body(workspace, symbol)
    except ValueError:
        body = symbol.preview
    if body:
        placeholders = re.findall(r"\{\{[^}]+\}\}", body)
        if placeholders:
            parts.append(" ".join(dict.fromkeys(placeholders)))
        for m in re.finditer(r'data-(?:proposal-[a-z-]+|proposal-bind)\s*=\s*["\']([^"\']+)["\']', body):
            parts.append(f"data-bind:{m.group(1)}")
        for m in re.finditer(r'\bclass\s*=\s*["\']([^"\']+)["\']', body[:6000]):
            for cls in m.group(1).split()[:12]:
                if cls.strip():
                    parts.append(cls.strip())
        if symbol.kind == "css_rule" and "{" in body:
            sel = body.split("{", 1)[0].strip().replace("\n", " ")
            if sel:
                parts.append(sel[:240])
    return " ".join(p for p in parts if p)


def _legacy_line_search(
    workspace: TemplateWorkspace,
    file: TemplateFile,
    query: str,
    *,
    use_regex: bool,
    max_hits: int,
) -> list[dict[str, Any]]:
    text = workspace.get_file(file)
    hits: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        matched = False
        if use_regex:
            try:
                matched = re.search(query, line) is not None
            except re.error:
                raise
        else:
            matched = query in line
        if matched:
            hits.append(
                {
                    "match_type": "line",
                    "line": i,
                    "text": line.strip()[:240],
                }
            )
        if len(hits) >= max_hits:
            break
    return hits


def execute_search_template(
    workspace: TemplateWorkspace,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Hybrid structure search (default): rank CSS rules, HTML sections/elements, JS symbols
    via local semantic + keyword embeddings — then return symbol_id + line span for
    read_template_symbol / replace_lines.

    mode=line or regex=true falls back to capped line grep (syntax-level queries only).
    """
    raw_file = str(arguments.get("file") or "html").strip().lower()
    query = str(arguments.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "query is required"}
    use_regex = bool(arguments.get("regex"))
    mode = str(arguments.get("mode") or "hybrid").strip().lower()
    kind = str(arguments.get("kind") or "all").strip().lower()
    if kind not in KIND_FILTER:
        kind = "all"
    max_hits = min(40, max(1, int(arguments.get("max_hits") or 12)))

    if mode == "line" or use_regex:
        try:
            file = normalize_template_file_arg(raw_file)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        try:
            line_hits = _legacy_line_search(
                workspace, file, query, use_regex=use_regex, max_hits=max_hits
            )
        except re.error as exc:
            return {"ok": False, "error": f"Invalid regex: {exc}"}
        return {
            "ok": True,
            "mode": "line",
            "file": file,
            "query": query,
            "hits": line_hits,
            "total_shown": len(line_hits),
            "context_note": (
                "Line mode — prefer mode=hybrid (default) for sections/CSS/JS structure; "
                "then read_template_symbol(symbol_id) instead of wide read_template_lines."
            ),
        }

    search_files: list[TemplateFile]
    if raw_file in ("all", "*", "any"):
        search_files = ["html", "css", "js"]
        file_label = "all"
    else:
        try:
            search_files = [normalize_template_file_arg(raw_file)]
            file_label = search_files[0]
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    candidates: list[TemplateSymbol] = []
    for f in search_files:
        syms = index_template_file(workspace, f)
        if kind != "all":
            syms = [s for s in syms if s.kind == kind]
        candidates.extend(syms)

    if not candidates:
        return {
            "ok": True,
            "mode": "hybrid",
            "file": file_label,
            "query": query,
            "hits": [],
            "total_shown": 0,
            "context_note": "No indexed symbols — append content or use read_template_lines on small ranges.",
        }

    q_lower = query.lower()
    scored: list[tuple[float, TemplateSymbol]] = []
    for sym in candidates:
        doc = _build_symbol_search_document(workspace, sym)
        score = hybrid_query_document_score(query, doc)
        if q_lower in doc.lower():
            score = min(1.0, score + 0.12)
        if sym.name.lower() == q_lower or q_lower in sym.name.lower():
            score = min(1.0, score + 0.08)
        scored.append((score, sym))
    scored.sort(key=lambda x: x[0], reverse=True)

    threshold = 0.035
    picked = [s for score, s in scored if score >= threshold][:max_hits]
    if not picked and scored:
        picked = [scored[0][1]]

    score_by_id = {sym.id: score for score, sym in scored}
    hits: list[dict[str, Any]] = []
    for sym in picked:
        hits.append(
            {
                "match_type": "symbol",
                "symbol_id": sym.id,
                "kind": sym.kind,
                "name": sym.name,
                "file": sym.id.split(":", 1)[0],
                "start_line": sym.start_line,
                "end_line": sym.end_line,
                "score": round(float(score_by_id.get(sym.id, 0.0)), 4),
                "preview": sym.preview[:200],
                "next_step": f'read_template_symbol(symbol_id="{sym.id}")',
            }
        )

    return {
        "ok": True,
        "mode": "hybrid",
        "file": file_label,
        "query": query,
        "kind": kind,
        "hits": hits,
        "total_shown": len(hits),
        "total_indexed": len(candidates),
        "context_note": (
            "Hybrid structure search (semantic + keyword on HTML sections, Tailwind classes, "
            "placeholders, CSS rules, inline script/style blocks). "
            "Use read_template_symbol on symbol_id — full section in one read — then replace_lines."
        ),
    }


def index_template_file(workspace: TemplateWorkspace, file: TemplateFile) -> list[TemplateSymbol]:
    key = _index_cache_key(workspace, file)
    cached = _index_cache.get(key)
    if cached is not None:
        return cached
    text = workspace.get_file(file)
    if file == "css":
        symbols = _extract_css_rules(text)
    elif file == "html":
        sections = _extract_proposal_sections(text)
        elements = _extract_html_elements(text)
        inline_css = _extract_inline_style_blocks(text)
        inline_js = _extract_inline_script_blocks(text)
        if sections:
            filtered = [e for e in elements if not _line_in_section_ranges(e.start_line, sections)]
            symbols = sections + filtered[:24] + inline_css[:6] + inline_js[:8]
        else:
            symbols = elements + inline_css[:6] + inline_js[:8]
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
    """Token-budgeted repo-map: proposal sections first, then css/js symbols."""
    lines = [
        "PROPOSAL SECTION POOL (each section = one HTML block with Tailwind classes + inline script):",
        "Use list_template_symbols(file=html, kind=proposal_section) then read_template_symbol(symbol_id) → replace_lines.",
    ]
    html_syms = index_template_file(workspace, "html")
    sections = [s for s in html_syms if s.kind == "proposal_section"]
    if sections:
        for s in sections[: max_per_file + 6]:
            span = s.end_line - s.start_line + 1
            lines.append(f"  • {s.id} — {s.name} (lines {s.start_line}-{s.end_line}, {span} lines)")
        extra = len(sections) - min(len(sections), max_per_file + 6)
        if extra > 0:
            lines.append(f"  … +{extra} more sections (list_template_symbols kind=proposal_section)")
    else:
        lines.append("  (no <section>/<main> blocks yet — use append_template or greenfield scaffold)")
    lines.append("")
    lines.append("OTHER TEMPLATE SYMBOLS (css rules, js functions, small html anchors):")
    for file in ("css", "html", "js"):
        syms = [s for s in index_template_file(workspace, file) if s.kind != "proposal_section"][:max_per_file]
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
    total_before_rank = len(syms)
    if query:
        scored: list[tuple[float, TemplateSymbol]] = []
        for s in syms:
            doc = f"{s.name} {s.preview}"
            scored.append((hybrid_query_document_score(query, doc), s))
        scored.sort(key=lambda x: x[0], reverse=True)
        syms = [s for score, s in scored if score > 0.04][:max_items]
        if not syms and scored:
            syms = [scored[0][1]]
        total = total_before_rank
    else:
        total = len(syms)
        syms = syms[:max_items]
    return {
        "ok": True,
        "file": file,
        "kind": kind,
        "symbols": [s.to_dict(include_lines=True) for s in syms],
        "total_matched": total,
        "shown": len(syms),
        "context_note": (
            "When `query` is set, results are ranked by hybrid semantic + keyword search "
            "(same local embeddings as designer agent rules). "
            "For proposal edits prefer kind=proposal_section — one read returns the full section "
            "(HTML + Tailwind + inline JS). Then replace_lines on that line range."
        ),
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
