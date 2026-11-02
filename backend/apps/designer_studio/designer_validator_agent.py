"""LangGraph validator agent — Muse + deterministic checks after executor (no separate architecture)."""
from __future__ import annotations

from typing import Any

from apps.rfp_debate.meta_client import MetaModelClient

from .designer_validation import gather_chat_validation_issues, should_skip_post_executor_validation


class DesignerValidatorAgent:
    """One-shot validation pass; repair is a separate LangGraph node using the executor repair loop."""

    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    def gather_issues(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        result: dict[str, Any],
    ) -> list[str]:
        return gather_chat_validation_issues(
            message=message,
            history=history,
            result=result,
            client=self.client,
        )

    @staticmethod
    def should_skip(result: dict[str, Any]) -> bool:
        return should_skip_post_executor_validation(result)
