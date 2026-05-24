# Module 6 — Rerank

Two-stage post-retrieval reranking: **Reciprocal Rank Fusion (RRF)** merges results from multiple retrieval strategies, then **Max Marginal Relevance (MMR)** selects a diverse top-k.

---

## Interface

```python
from modules.module6_rerank.pipeline import rerank

results: list[RetrievalResult] = rerank(
    query="metformin glycemic control",
    query_vector=[...],           # dense embedding of the query
    retrieval_map={               # keyed by strategy
        "semantic": [...],        # RetrievalResult[]
        "lexical":  [...],
        "hybrid":   [...],
    },
    rrf_top_n=20,                 # candidates passed to MMR
    mmr_top_k=8,                  # final result count
    lambda_param=0.7,             # relevance vs diversity trade-off
)
```

No Celery tasks — called synchronously from Module 7 agent tools.

---

## Pipeline (`pipeline.py`)

```mermaid
flowchart TD
    R1[semantic results] --> RRF
    R2[lexical results]  --> RRF
    R3[hybrid results]   --> RRF

    RRF["Stage 1: RRF\nreciprocal_rank_fusion()\nall strategies → top_n"]
    RRF --> VFETCH["fetch_vectors_from_qdrant(top_n IDs)"]
    VFETCH --> MMR["Stage 2: MMR\nmax_marginal_relevance()\ntop_n → top_k"]
    MMR --> OUT[top_k RetrievalResult[]]
```

1. **RRF** fuses all retrieval lists into a single ranked list, taking `rrf_top_n` candidates.
2. The dense vectors for those `rrf_top_n` chunks are fetched from Qdrant (needed for cosine-sim in MMR).
3. **MMR** selects `mmr_top_k` diverse results from the candidates.
4. The entire pipeline is timed and reported to `rerank_latency_seconds`.

---

## Stage 1 — Reciprocal Rank Fusion (`rrf.py`)

### Formula

$$\text{score}(d) = \sum_{i} \frac{1}{k + \text{rank}_i(d)}$$

- `k = 60` (standard smoothing constant)
- Rank is **1-indexed** (best = rank 1)
- Documents absent from a list contribute 0 for that list

### Implementation

```python
def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalResult]],
    k: int = 60,
) -> list[RetrievalResult]:
```

- All lists are iterated; scores accumulated in a `dict[chunk_id → score]`
- Results sorted descending by fused score
- Returns a flat `RetrievalResult[]` with updated `score` and `rank`

### Why RRF?

RRF is robust to score-scale differences between retrieval strategies — a chunk ranked #1 by semantic and #3 by lexical gets a higher combined score regardless of the raw float values each system returned. It requires no training and generalises well across query types.

---

## Stage 2 — Max Marginal Relevance (`mmr.py`)

### Formula

$$\text{MMR}(d) = \lambda \cdot \text{sim}(d, q) - (1-\lambda) \cdot \max_{s \in S} \text{sim}(d, s)$$

- $q$ = query vector
- $S$ = set of already-selected documents
- $\lambda = 0.7$ → 70 % relevance weight, 30 % diversity

### Implementation

```python
def max_marginal_relevance(
    query_vector: list[float],
    candidates: list[RetrievalResult],
    candidate_vectors: dict[str, list[float]],  # chunk_id → dense vector
    top_k: int = 8,
    lambda_param: float = 0.7,
) -> list[RetrievalResult]:
```

Greedy selection loop:

1. First pick: highest cosine similarity to query.
2. Each subsequent pick: maximise MMR score — most relevant among least similar to already-selected.
3. Repeat until `top_k` or candidates exhausted.

The `mmr_score` inner function binds `sel_vecs` as a default argument to avoid the loop-variable closure bug (B023).

### `cosine_sim(a, b)`

```python
def cosine_sim(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0
```

Zero-vector guard returns 0.0 rather than NaN.

---

## Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `rrf_top_n` | 20 | Candidates fed to MMR; higher = broader diversity pool |
| `mmr_top_k` | 8 | Final chunks returned to the agent |
| `lambda_param` | 0.7 | 1.0 = pure relevance; 0.0 = pure diversity |
| RRF `k` | 60 | Smoothing; lower = more rank-sensitive |

---

## Concurrency & Scaling

- RRF and MMR are pure CPU/NumPy operations — microseconds to low milliseconds for typical `top_n`.
- `fetch_vectors_from_qdrant()` is a single Qdrant point-fetch call — fast even at `top_n=100`.
- No parallelism required. Bottleneck is the upstream retrieval, not reranking.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Chunk ID not in `candidate_vectors` | Chunk skipped in MMR (only available vectors used) |
| Empty retrieval lists | RRF returns empty list; MMR returns empty list |
| Zero-magnitude vectors | `cosine_sim` returns 0.0 safely |

---

## Observability

| Signal | Detail |
|--------|--------|
| `rerank_latency_seconds` | Histogram — full RRF + vector fetch + MMR wall time |
