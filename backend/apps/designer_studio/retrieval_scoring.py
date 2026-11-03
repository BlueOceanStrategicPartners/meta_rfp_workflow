"""Lexical + semantic ranking for Designer Studio (BM25 + local embeddings).

BM25 (Okapi) improves template symbol search vs raw token overlap: it respects
term frequency saturation, document length, and inverse document frequency across
the symbol corpus (room block, section#rooms, Tailwind class tokens, etc.).
"""
from __future__ import annotations

import math
from typing import Sequence

from .agent_rules import cosine, embed_rule_text, tokenize

BM25_K1 = 1.5
BM25_B = 0.75


class BM25Index:
    """Okapi BM25 over a tokenized corpus (one query scores all documents)."""

    def __init__(
        self,
        corpus_tokens: Sequence[Sequence[str]],
        *,
        k1: float = BM25_K1,
        b: float = BM25_B,
    ):
        self.k1 = k1
        self.b = b
        self.corpus = [list(doc) for doc in corpus_tokens]
        self.nd = len(self.corpus)
        self.avgdl = sum(len(d) for d in self.corpus) / max(self.nd, 1)
        df: dict[str, int] = {}
        for doc in self.corpus:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1
        self.idf = {
            term: math.log(1.0 + (self.nd - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def score_document(self, query_tokens: Sequence[str], doc_tokens: Sequence[str]) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        dl = len(doc_tokens)
        tf_map: dict[str, int] = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1
        score = 0.0
        for term in query_tokens:
            if term not in self.idf:
                continue
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue
            idf = self.idf[term]
            denom = tf + self.k1 * (1.0 - self.b + self.b * dl / max(self.avgdl, 1.0))
            score += idf * (tf * (self.k1 + 1.0)) / max(denom, 1e-9)
        return score

    def score_query(self, query: str) -> list[float]:
        q_tokens = tokenize(query)
        return [self.score_document(q_tokens, doc) for doc in self.corpus]


def _normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo = min(scores)
    hi = max(scores)
    if hi <= lo + 1e-12:
        return [0.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def hybrid_rank_documents(
    query: str,
    documents: Sequence[str],
    *,
    semantic_weight: float = 0.48,
    bm25_weight: float = 0.42,
    substring_weight: float = 0.10,
) -> list[float]:
    """Rank documents: BM25 (corpus-aware) + deterministic embedding cosine + substring."""
    q = (query or "").strip()
    docs = [(d or "").strip() for d in documents]
    if not q or not docs:
        return [0.0] * len(docs)

    q_embed = embed_rule_text(q)
    q_lower = q.lower()
    sem_scores = [cosine(q_embed, embed_rule_text(d)) for d in docs]
    bm25 = BM25Index([tokenize(d) for d in docs])
    bm25_raw = bm25.score_query(q)
    bm25_norm = _normalize_scores(bm25_raw)
    sub_scores = [1.0 if q_lower in d.lower() else 0.0 for d in docs]

    out: list[float] = []
    for i in range(len(docs)):
        combined = (
            semantic_weight * sem_scores[i]
            + bm25_weight * bm25_norm[i]
            + substring_weight * sub_scores[i]
        )
        out.append(min(1.0, combined))
    return out


def hybrid_query_document_score(query: str, document: str) -> float:
    """Single-document hybrid score (BM25 degenerates to one doc — still uses TF/length)."""
    scores = hybrid_rank_documents(query, [document])
    return scores[0] if scores else 0.0
