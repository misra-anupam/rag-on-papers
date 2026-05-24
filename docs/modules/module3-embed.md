# Module 3 — Embed

Generates dense (OpenRouter `text-embedding-3-large`) and sparse (SPLADE_PP) vectors for every chunk, then re-uploads the augmented JSONL and chains to Module 4.

---

## Entrypoint

```python
embed_chunks(doi: str)
```

- **File**: `modules/module3_embed/tasks.py`
- `max_retries=3`

---

## Execution Flow

```mermaid
sequenceDiagram
    participant Task as embed_chunks
    participant S3 as S3
    participant Dense as dense.py (async)
    participant OR as OpenRouter\n/v1/embeddings
    participant Sparse as sparse.py (CPU)
    participant SPLADE as fastembed SPLADE_PP
    participant Registry as PostgreSQL registry
    participant Next as ingest_to_qdrant (M4)

    Task->>S3: load_chunks_from_s3(doi) → [Chunk]
    Task->>Dense: embed_texts([text_with_header, ...])

    Note over Dense,OR: Batch size=100, concurrency=5
    Dense->>OR: POST /v1/embeddings (batch 0..99)
    Dense->>OR: POST /v1/embeddings (batch 100..199)
    Dense->>OR: ... (all concurrent up to semaphore=5)
    OR-->>Dense: [[float × 512], ...]
    Dense-->>Task: dense_vectors

    Task->>Sparse: generate_sparse_vectors([text_with_header, ...])
    Sparse->>SPLADE: model.embed(texts)
    SPLADE-->>Sparse: SparseEmbedding[]
    Sparse-->>Task: [{indices, values}, ...]

    Task->>Task: augment each Chunk with dense_vector, sparse_indices, sparse_values
    Task->>S3: save_chunks_to_s3(chunks, doi)  [overwrite JSONL]
    Task->>Registry: registry.update(doi, embed_status="embedded")
    Task->>Next: ingest_to_qdrant.delay(doi)
```

---

## Dense Embedding (`dense.py`)

### Model

| Setting | Value |
|---------|-------|
| Provider | OpenRouter → OpenAI |
| Model ID | `openai/text-embedding-3-large` |
| Dimensions | `512` (via `dimensions` param) |
| Input | `chunk.text_with_header` (header-injected text) |

### Batching & Concurrency

```python
BATCH_SIZE = 100          # texts per API request
semaphore = asyncio.Semaphore(5)  # max 5 concurrent batches
```

`embed_texts()` is `async`. It creates all batch coroutines and runs them with `asyncio.gather` gated by the semaphore. With 200 chunks this means 2 concurrent requests; with 1 000 chunks, 5 run at a time.

### Retry

Each `_embed_batch()` call is wrapped with Tenacity:

```python
@tenacity.retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(httpx.HTTPError),
)
```

### Token Tracking

After each batch, `openrouter_tokens_total{model, type="total"}` is incremented from the `usage.total_tokens` field in the API response.

---

## Sparse Embedding (`sparse.py`)

### Model

| Setting | Value |
|---------|-------|
| Library | `fastembed` |
| Model | `prithivida/Splade_PP_en_v1` |
| Cache | `~/.cache/fastembed` (~500 MB download on first run) |
| Hardware | CPU only |

### Implementation

```python
@lru_cache(maxsize=1)
def _load_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

def generate_sparse_vectors(texts: list[str]) -> list[dict]:
    model = _load_model()
    return [
        {"indices": emb.indices.tolist(), "values": emb.values.tolist()}
        for emb in model.embed(texts)
    ]
```

The model is loaded **once per worker process** via `lru_cache` — subsequent calls reuse the same in-memory model.

!!! note "Memory"
    SPLADE_PP loads ~500 MB into RAM. Workers running embed tasks need at least 1.5 GB free.

---

## Concurrency & Scaling

```mermaid
flowchart LR
    A[embed_chunks task] --> B[asyncio event loop\ninside worker]
    B --> C[Semaphore 5]
    C --> D1[OR batch 0]
    C --> D2[OR batch 1]
    C --> D3[OR batch 2]
    C --> D4[OR batch 3]
    C --> D5[OR batch 4]
    B --> E[SPLADE CPU\nsequential after dense]
```

- Dense embedding is **I/O-bound** — concurrency of 5 batches maximises OpenRouter throughput.
- Sparse embedding is **CPU-bound** — runs sequentially after dense embedding completes.
- The overall task runs inside `asyncio.run()` (invoked by the synchronous Celery wrapper).
- To scale throughput, add more Celery workers — each runs its own event loop and SPLADE model instance.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| OpenRouter HTTP error | Tenacity retries up to 5× per batch |
| Tenacity exhausted | Exception propagates → Celery retry (max 3) |
| SPLADE model load fails | Exception → Celery retry |
| S3 upload fails | Exception → Celery retry |

---

## Observability

| Signal | Detail |
|--------|--------|
| `embedding_latency_seconds` | Histogram — total wall time for all batches |
| `openrouter_tokens_total{model, type="total"}` | Accumulated from each batch response |
