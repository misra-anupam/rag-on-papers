from modules.module5_retrieve.base import RetrievalResult


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalResult]],
    k: int = 60,
) -> list[RetrievalResult]:
    """
    score(d) = sum_i  1 / (k + rank_i(d))
    rank is 1-indexed; documents missing from a list score 0 for that list.
    """
    scores:   dict[str, float] = {}
    payloads: dict[str, dict]  = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list):
            cid = result.chunk_id
            scores[cid]   = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            payloads[cid] = result.payload

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        RetrievalResult(cid, scores[cid], payloads[cid], i, 'rrf')
        for i, cid in enumerate(sorted_ids)
    ]
