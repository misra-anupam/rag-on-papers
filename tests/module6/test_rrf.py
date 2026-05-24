from modules.module5_retrieve.base import RetrievalResult
from modules.module6_rerank.rrf import reciprocal_rank_fusion


def _r(cid, score=0.9, rank=0):
    return RetrievalResult(cid, score, {"doi": "10/test"}, rank, "test")


def test_rrf_overlapping_doc_scores_higher():
    list_a = [_r("A"), _r("B"), _r("C")]
    list_b = [_r("B"), _r("D"), _r("E")]
    fused = reciprocal_rank_fusion([list_a, list_b])

    # B appears in both lists so should rank higher than A or D
    ids = [r.chunk_id for r in fused]
    assert ids.index("B") < ids.index("A")
    assert ids.index("B") < ids.index("D")


def test_rrf_scores_sum_correctly():
    list_a = [_r("X")]
    list_b = [_r("X")]
    fused = reciprocal_rank_fusion([list_a, list_b], k=60)
    # X appears rank 0 in both: score = 1/61 + 1/61
    expected = 2 / 61
    assert abs(fused[0].score - expected) < 1e-9


def test_rrf_missing_document_scores_zero_contribution():
    list_a = [_r("A"), _r("B")]
    list_b = [_r("C")]
    fused = reciprocal_rank_fusion([list_a, list_b])
    # A is only in list_a, C only in list_b; B only in list_a
    ids = [r.chunk_id for r in fused]
    assert set(ids) == {"A", "B", "C"}


def test_rrf_strategy_label():
    fused = reciprocal_rank_fusion([[_r("X")]])
    assert fused[0].strategy == "rrf"
