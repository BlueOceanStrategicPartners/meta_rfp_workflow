"""Revision snapshots on template save."""
from __future__ import annotations

from django.utils import timezone

from .models import ProposalTemplate

MAX_REVISIONS = 15


def append_revision(template: ProposalTemplate, *, note: str = "save") -> None:
    entry = {
        "saved_at": timezone.now().isoformat(),
        "note": note,
        "name": template.name,
        "html_markup": template.html_markup,
        "css_stylesheet": template.css_stylesheet,
        "js_script": template.js_script,
    }
    history = list(template.revision_history_json or [])
    history.insert(0, entry)
    template.revision_history_json = history[:MAX_REVISIONS]
