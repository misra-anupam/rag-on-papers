from unittest.mock import patch

from modules.module5_retrieve.base import RetrievalResult


def _r(cid, score=0.9, rank=0):
    return RetrievalResult(cid, score, {"doi": "10/test", "text": ""}, rank, "test")


def test_rerank_returns_mmr_top_k():
    semantic_results = [_r(str(i), rank=i) for i in range(5)]
    lexical_results = [_r(str(i + 2), rank=i) for i in range(5)]
    query_vector = [0.1] * 512

    fake_vectors = {
        r.chunk_id: [float(int(r.chunk_id)) / 10] * 512 for r in semantic_results + lexical_results
    }

    with patch(
        "modules.module6_rerank.pipeline.fetch_vectors_from_qdrant", return_value=fake_vectors
    ):
        from modules.module6_rerank.pipeline import rerank

        result = rerank(
            query="test query",
            query_vector=query_vector,
            retrieval_map={"semantic": semantic_results, "lexical": lexical_results},
            rrf_top_n=7,
            mmr_top_k=3,
        )

    assert len(result) <= 3


def test_rerank_empty_results():
    with patch("modules.module6_rerank.pipeline.fetch_vectors_from_qdrant", return_value={}):
        from modules.module6_rerank.pipeline import rerank

        result = rerank(
            query="nothing",
            query_vector=[0.0] * 512,
            retrieval_map={"semantic": []},
        )
    assert result == []
