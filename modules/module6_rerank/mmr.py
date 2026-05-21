import numpy as np

from modules.module5_retrieve.base import RetrievalResult


def cosine_sim(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom  = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def max_marginal_relevance(
    query_vector:      list[float],
    candidates:        list[RetrievalResult],
    candidate_vectors: dict[str, list[float]],
    top_k:             int   = 8,
    lambda_param:      float = 0.7,
) -> list[RetrievalResult]:
    # Only consider candidates whose vector we actually fetched
    available  = [r for r in candidates if r.chunk_id in candidate_vectors]
    selected:  list[RetrievalResult] = []
    remaining: list[RetrievalResult] = list(available)

    while remaining and len(selected) < top_k:
        if not selected:
            best = max(
                remaining,
                key=lambda r: cosine_sim(candidate_vectors[r.chunk_id], query_vector),
            )
        else:
            sel_vecs = [candidate_vectors[s.chunk_id] for s in selected]

            def mmr_score(r: RetrievalResult) -> float:
                rel = cosine_sim(candidate_vectors[r.chunk_id], query_vector)
                red = max(cosine_sim(candidate_vectors[r.chunk_id], sv) for sv in sel_vecs)
                return lambda_param * rel - (1 - lambda_param) * red

            best = max(remaining, key=mmr_score)

        selected.append(best)
        remaining.remove(best)

    return selected
