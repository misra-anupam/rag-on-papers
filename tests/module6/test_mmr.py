import numpy as np
from modules.module5_retrieve.base import RetrievalResult
from modules.module6_rerank.mmr import cosine_sim, max_marginal_relevance


def _r(cid, score=0.9):
    return RetrievalResult(cid, score, {}, 0, 'test')


def test_cosine_sim_identical():
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_sim(v, v) - 1.0) < 1e-9


def test_cosine_sim_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_sim(a, b)) < 1e-9


def test_mmr_selects_top_k():
    query_vec = [1.0, 0.0, 0.0]
    candidates = [_r('A'), _r('B'), _r('C'), _r('D')]
    vecs = {
        'A': [1.0, 0.0, 0.0],
        'B': [0.9, 0.1, 0.0],
        'C': [0.0, 1.0, 0.0],
        'D': [0.0, 0.0, 1.0],
    }
    result = max_marginal_relevance(query_vec, candidates, vecs, top_k=2)
    assert len(result) == 2


def test_mmr_avoids_near_duplicate():
    """Two nearly identical candidates should not both appear in top-2."""
    query_vec = [1.0, 0.0]
    candidates = [_r('A'), _r('B'), _r('C')]
    vecs = {
        'A': [1.0, 0.0],     # very relevant
        'B': [0.99, 0.01],   # near duplicate of A
        'C': [0.0, 1.0],     # diverse
    }
    result = max_marginal_relevance(
        query_vec, candidates, vecs, top_k=2, lambda_param=0.5
    )
    ids = {r.chunk_id for r in result}
    # With diversity weighting, should prefer A+C over A+B
    assert 'A' in ids
    assert 'C' in ids


def test_mmr_returns_at_most_top_k():
    query_vec = [1.0, 0.0]
    candidates = [_r(str(i)) for i in range(10)]
    vecs = {str(i): [float(i) / 10, 0.0] for i in range(10)}
    result = max_marginal_relevance(query_vec, candidates, vecs, top_k=3)
    assert len(result) <= 3
