"""In-memory proposal template workspace (html / css / js) with line-oriented editing."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from apps.designer_studio.models import REQUIRED_PLACEHOLDERS

TemplateFile = Literal["html", "css", "js"]

_FILE_ARG_ALIASES: dict[str, TemplateFile] = {
    "html": "html",
    "html_markup": "html",
    "markup": "html",
    "css": "css",
    "css_stylesheet": "css",
    "stylesheet": "css",
    "js": "js",
    "javascript": "js",
    "js_script": "js",
    "script": "js",
}


def normalize_template_file_arg(raw: Any) -> TemplateFile:
    """Map tool `file` args (html/css/js or API field names) to workspace file keys."""
    name = str(raw or "html").strip().lower()
    if name in _FILE_ARG_ALIASES:
        return _FILE_ARG_ALIASES[name]
    raise ValueError(f"Unknown file '{raw}'. Use html, css, or js (not html_markup / css_stylesheet).")


class TemplateFileKey(str, Enum):
    HTML = "html"
    CSS = "css"
    JS = "js"


FILE_FIELD: dict[TemplateFile, str] = {
    "html": "html_markup",
    "css": "css_stylesheet",
    "js": "js_script",
}


@dataclass
class TemplateWorkspace:
    html_markup: str = ""
    css_stylesheet: str = ""
    js_script: str = ""

    def get_file(self, file: TemplateFile) -> str:
        if file == "html":
            return self.html_markup
        if file == "css":
            return self.css_stylesheet
        return self.js_script

    def set_file(self, file: TemplateFile, content: str) -> None:
        if file == "html":
            self.html_markup = content
        elif file == "css":
            self.css_stylesheet = content
        else:
            self.js_script = content

    def line_count(self, file: TemplateFile) -> int:
        text = self.get_file(file)
        if not text:
            return 0
        return len(text.splitlines())

    def read_lines(self, file: TemplateFile, start_line: int, end_line: int) -> str:
        lines = self.get_file(file).splitlines()
        if not lines and start_line == 1 and end_line >= 1:
            return ""
        n = len(lines)
        start = max(1, int(start_line))
        end = min(n, int(end_line))
        if start > n or start > end:
            raise ValueError(f"Line range {start_line}-{end_line} out of range for {file} ({n} lines)")
        chunk = lines[start - 1 : end]
        return "\n".join(f"{i + start:5d}| {line}" for i, line in enumerate(chunk))

    def replace_lines(self, file: TemplateFile, start_line: int, end_line: int, new_content: str) -> None:
        lines = self.get_file(file).splitlines()
        n = len(lines)
        start = int(start_line)
        end = int(end_line)
        if start < 1 or end < start or (n and start > n):
            raise ValueError(f"Invalid line range {start}-{end} for {file} ({n} lines)")
        new_lines = new_content.splitlines()
        if end > n:
            end = n
        head = lines[: start - 1]
        tail = lines[end:]
        self.set_file(file, "\n".join(head + new_lines + tail))

    def append(self, file: TemplateFile, content: str) -> None:
        current = self.get_file(file)
        if not current:
            self.set_file(file, content.lstrip("\n"))
            return
        sep = "" if current.endswith("\n") or not content else "\n"
        self.set_file(file, current + sep + content)

    def to_result_dict(self) -> dict[str, str]:
        return {
            "html_markup": self.html_markup,
            "css_stylesheet": self.css_stylesheet,
            "js_script": self.js_script,
        }

    def placeholder_report(self) -> dict[str, list[str]]:
        html = self.html_markup or ""
        present = [p for p in REQUIRED_PLACEHOLDERS if p in html]
        missing = [p for p in REQUIRED_PLACEHOLDERS if p not in html]
        return {"present": present, "missing": missing}
