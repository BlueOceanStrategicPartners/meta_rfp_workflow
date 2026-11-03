from apps.designer_studio.agent_rules import tokenize
from apps.designer_studio.retrieval_scoring import BM25Index, hybrid_rank_documents


def test_bm25_prefers_matching_section():
    docs = [
        "section#welcome hero banner client_name",
        "section#rooms verified_room_blocks table tbody line_items",
        "section#meetings av setup capacity",
    ]
    scores = hybrid_rank_documents("verified room block table", docs)
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_bm25_index_scores_room_section_highest():
    corpus = [
        tokenize("section block table data"),
        tokenize("section block map venue"),
        tokenize("footer legal copyright"),
        tokenize("section#rooms room block table verified_room_blocks"),
    ]
    idx = BM25Index(corpus)
    scores = idx.score_query("room block table")
    assert scores[3] >= max(scores[0], scores[1], scores[2])
