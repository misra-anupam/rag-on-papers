import time

from modules.module5_retrieve.base import RetrievalResult
from modules.module6_rerank.mmr import max_marginal_relevance
from modules.module6_rerank.rrf import reciprocal_rank_fusion
from shared.observability import rerank_latency


def rerank(
    query: str,
    query_vector: list[float],
    retrieval_map: dict[str, list[RetrievalResult]],
    rrf_top_n: int = 20,
    mmr_top_k: int = 8,
    lambda_param: float = 0.7,
) -> list[RetrievalResult]:
    t0 = time.perf_counter()

    # Stage 1: RRF — fuse all retriever outputs
    fused = reciprocal_rank_fusion(list(retrieval_map.values()))
    top_n = fused[:rrf_top_n]

    if not top_n:
        return []

    # Fetch dense vectors for MMR similarity computation
    ids = [r.chunk_id for r in top_n]
    from modules.module4_index.ingest import fetch_vectors_from_qdrant

    vectors = fetch_vectors_from_qdrant(ids)

    # Stage 2: MMR — diverse final selection
    result = max_marginal_relevance(
        query_vector,
        top_n,
        vectors,
        top_k=mmr_top_k,
        lambda_param=lambda_param,
    )
    rerank_latency.observe(time.perf_counter() - t0)
    return result
