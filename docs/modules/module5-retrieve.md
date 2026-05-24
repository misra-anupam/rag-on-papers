# Module 5 — Retrieve

Provides three retrieval strategies — semantic (dense ANN), lexical (sparse SPLADE), and hybrid (server-side RRF fusion) — with a unified interface and optional metadata pre-filtering.

---

## Interface

```python
retriever = get_retriever(strategy)          # "semantic" | "lexical" | "hybrid"
results: list[RetrievalResult] = retriever.retrieve(
    query="metformin HbA1c randomised trial",
    top_k=100,
    filters={"mesh_terms": ["Metformin"], "year_from": 2020},
)
```

**File**: `modules/module5_retrieve/`

No Celery tasks — this module is called synchronously at query time from Module 7 (agent tools).

---

## `RetrievalResult`

```python
@dataclass
class RetrievalResult:
    chunk_id: str
    score: float
    payload: dict        # full Qdrant payload (text, doi, section_heading, ...)
    rank: int
    strategy: str        # "semantic" | "lexical" | "hybrid"
```

---

## Strategies

### Semantic (`semantic.py`)

Dense vector ANN search.

```mermaid
flowchart LR
    Q[query string] --> E[embed_texts\ntext-embedding-3-large\n512-dim]
    E --> QD[Qdrant\nnamedVector='dense'\nHNSW ANN]
    QD --> R[RetrievalResult[]]
```

```python
query_vec = await embed_texts([query])[0]
client.search(
    collection_name=COLLECTION,
    query_vector=NamedVector(name="dense", vector=query_vec),
    query_filter=build_filter(filters),
    limit=top_k,
    with_payload=True,
)
```

### Lexical (`lexical.py`)

Sparse SPLADE vector search — term-level matching with learned expansion.

```mermaid
flowchart LR
    Q[query string] --> SP[generate_sparse_vectors\nSPLADE_PP_en_v1]
    SP --> QD[Qdrant\nnamedSparseVector='sparse']
    QD --> R[RetrievalResult[]]
```

```python
sv = generate_sparse_vectors([query])[0]
client.search(
    collection_name=COLLECTION,
    query_vector=NamedSparseVector(
        name="sparse",
        vector=SparseVector(indices=sv["indices"], values=sv["values"]),
    ),
    query_filter=build_filter(filters),
    limit=top_k,
    with_payload=True,
)
```

### Hybrid (`hybrid.py`)

Dense + sparse **server-side fusion** using Qdrant's `Fusion.RRF`.

```mermaid
flowchart LR
    Q[query string]
    Q --> E[Dense embed]
    Q --> SP[Sparse embed]
    E --> PF1[Prefetch dense top_k]
    SP --> PF2[Prefetch sparse top_k]
    PF1 & PF2 --> QD[Qdrant\nFusionQuery RRF]
    QD --> R[RetrievalResult[]]
```

```python
client.query_points(
    collection_name=COLLECTION,
    prefetch=[
        Prefetch(using="dense", query=dense_vec, limit=top_k),
        Prefetch(using="sparse", query=sparse_vec, limit=top_k),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    query_filter=build_filter(filters),
    limit=top_k,
    with_payload=True,
)
```

The `fusion=Fusion.RRF` fusion happens **inside Qdrant** — no additional round-trip needed.

---

## Filter Building (`tag.py`)

`build_filter(filters: dict) -> Filter | None`

| Filter key | Qdrant condition | Notes |
|-----------|-----------------|-------|
| `mesh_terms` | `MatchAny` | Matches any term in the list |
| `year_from` | `Range(gte=year)` | Inclusive lower bound on `pub_year` |
| `year_to` | `Range(lte=year)` | Inclusive upper bound on `pub_year` |
| `journal` | `MatchValue` | Exact string match |
| `element_type` | `MatchValue` | `abstract \| section \| figure \| table` |
| `source_db` | `MatchValue` | `pubmed \| europepmc \| ...` |

Multiple conditions are combined as `Filter(must=[...])` — all must match.

Returns `None` when no filters are provided (no Qdrant filter param sent).

---

## Concurrency & Scaling

- All three retrievers are **synchronous** at the Python level (Qdrant client is sync).
- Dense embedding for the query uses the same async `embed_texts()` wrapper, called via `asyncio.run()`.
- Retrieval itself is a single Qdrant network call — fast (<50 ms typical).
- No internal concurrency; multiple concurrent queries simply open multiple Qdrant connections.
- Qdrant is the scaling surface — deploy a clustered Qdrant for higher QPS.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Qdrant connection failure | Exception propagates to caller (Module 7 tool) |
| Empty result set | Returns empty list — caller decides next step |
| Embedding failure | Exception propagates (Tenacity inside `embed_texts`) |
| Invalid strategy string | `ValueError` raised by `get_retriever()` |

---

## Observability

| Signal | Detail |
|--------|--------|
| `retrieval_latency_seconds{strategy=...}` | Histogram per `retrieve()` call, all three strategies |
