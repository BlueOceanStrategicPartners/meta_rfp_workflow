"""Designer agent rules — local embeddings (SQLite) + BM25/semantic hybrid RAG."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from django.conf import settings

from apps.rfp_debate.meta_client import MetaModelClient

from .muse_client import designer_agent_model_id

from .models import DesignerAgentRule

EMBED_DIM = 256
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)

RULE_CONFLICT_SYSTEM = (
    "You validate hospitality proposal design agent rules for internal consistency. "
    "Return JSON only: has_conflict (boolean), explanation (string), "
    "conflicting_rule_ids (string array of UUIDs), suggested_rule (string, optional merged rule text). "
    "Flag conflicts when two rules give incompatible layout, branding, CTA, map, or copy instructions."
)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def embed_rule_text(text: str) -> list[float]:
    """Deterministic local embedding (stored in SQLite; sync to Azure vector index in production)."""
    vec = [0.0] * EMBED_DIM
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(EMBED_DIM):
            byte = digest[i % len(digest)]
            vec[i] += (byte / 255.0) * 2.0 - 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def keyword_score(query_tokens: set[str], rule_tokens: list[str]) -> float:
    if not query_tokens or not rule_tokens:
        return 0.0
    rule_set = set(rule_tokens)
    overlap = len(query_tokens & rule_set)
    return overlap / max(len(query_tokens), 1)


def hybrid_score(
    query_embed: list[float],
    query_tokens: set[str],
    rule: DesignerAgentRule,
    *,
    bm25_norm: float = 0.0,
) -> float:
    sem = cosine(query_embed, rule.embedding_json or [])
    if bm25_norm > 0.0:
        return 0.55 * sem + 0.45 * bm25_norm
    kw = keyword_score(query_tokens, rule.search_tokens_json or [])
    return 0.62 * sem + 0.38 * kw


def hybrid_query_document_score(query: str, document: str) -> float:
    """Local semantic + BM25 + substring (see retrieval_scoring.hybrid_rank_documents)."""
    from .retrieval_scoring import hybrid_query_document_score as _score

    return _score(query, document)


def retrieve_relevant_rules(
    designer_id: int,
    query: str,
    *,
    limit: int = 8,
) -> list[DesignerAgentRule]:
    rules = list(
        DesignerAgentRule.objects.filter(designer_id=designer_id).order_by("sort_order", "created_at")
    )
    if not rules:
        return []
    from .retrieval_scoring import hybrid_rank_documents

    bodies = [(r.body or "") for r in rules]
    rank_scores = hybrid_rank_documents(query, bodies)
    scored = [(rank_scores[i], r) for i, r in enumerate(rules)]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [r for score, r in scored if score > 0.05][:limit]
    if not top and rules:
        return rules[: min(limit, len(rules))]
    return top


def format_rules_for_agent(rules: list[DesignerAgentRule]) -> str:
    if not rules:
        return ""
    lines = [
        "DESIGN AGENT RULES (user-defined — follow all that apply; do not contradict without noting tradeoff):"
    ]
    for i, rule in enumerate(rules, start=1):
        body = (rule.body or "").strip().replace("\n", " ")
        lines.append(f"{i}. [{rule.id}] {body[:800]}")
    lines.append("Before finishing, verify your output respects these rules.")
    return "\n".join(lines)


def refresh_rule_vectors(rule: DesignerAgentRule) -> None:
    rule.embedding_json = embed_rule_text(rule.body)
    rule.search_tokens_json = tokenize(rule.body)
    rule.save(update_fields=["embedding_json", "search_tokens_json", "updated_at"])


def validate_rule_conflict(
    *,
    designer_id: int,
    new_body: str,
    exclude_rule_id: str | None = None,
) -> dict[str, Any]:
    existing = DesignerAgentRule.objects.filter(designer_id=designer_id).order_by("sort_order", "created_at")
    if exclude_rule_id:
        existing = existing.exclude(pk=exclude_rule_id)
    catalog = [
        {"id": str(r.id), "body": r.body[:1200]}
        for r in existing[:200]
    ]
    if not catalog:
        return {"has_conflict": False, "explanation": "", "conflicting_rule_ids": [], "suggested_rule": ""}

    if settings.USE_FIXTURE_DEBATE or not getattr(settings, "META_MODEL_API_KEY", ""):
        return _fixture_validate_conflict(new_body, catalog)

    client = MetaModelClient()
    user_payload = (
        f"New or updated rule:\n{new_body.strip()[:2000]}\n\n"
        f"Existing rules JSON:\n{catalog}"
    )
    raw = client.complete_json_messages(
        model_id=designer_agent_model_id(),
        messages=[
            {"role": "system", "content": RULE_CONFLICT_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        fixture_kind="designer_rule_validate",
    )
    return {
        "has_conflict": bool(raw.get("has_conflict")),
        "explanation": str(raw.get("explanation") or "").strip(),
        "conflicting_rule_ids": [
            str(x) for x in (raw.get("conflicting_rule_ids") or []) if x
        ],
        "suggested_rule": str(raw.get("suggested_rule") or "").strip(),
    }


def _fixture_validate_conflict(new_body: str, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    lower = new_body.lower()
    for item in catalog:
        prev = (item.get("body") or "").lower()
        if "always use light mode" in lower and "dark mode" in prev:
            return {
                "has_conflict": True,
                "explanation": "New rule prefers light mode but an existing rule requires dark mode.",
                "conflicting_rule_ids": [item["id"]],
                "suggested_rule": "Use dark luxury theme with light hero accents only.",
            }
        if "dark mode" in lower and "light mode" in prev:
            return {
                "has_conflict": True,
                "explanation": "New rule prefers dark mode but an existing rule requires light mode.",
                "conflicting_rule_ids": [item["id"]],
                "suggested_rule": "Use light editorial layout with dark footer band only.",
            }
    return {"has_conflict": False, "explanation": "", "conflicting_rule_ids": [], "suggested_rule": ""}
