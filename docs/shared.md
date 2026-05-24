# Shared Infrastructure

Components used by every module: Celery app, configuration, data models, database session, S3 client, observability, and utilities.

---

## Celery (`shared/celery_app.py`)

### Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| Broker | RabbitMQ (`AMQP_URL`) | Task message bus |
| Result backend | Redis (`REDIS_URL`) | Task state + results |
| Serializer | JSON | Human-readable payloads |
| `worker_prefetch_multiplier` | `1` | Fair dispatch — each worker takes one task at a time |
| `task_acks_late` | `True` | Acknowledge only after completion, so crashed workers re-queue |
| `task_track_started` | `True` | Report `STARTED` state for monitoring |

### Beat Schedule

```python
beat_schedule = {
    "fetch-pubmed-daily":           # 02:00 UTC, 500 results
    "fetch-europepmc-daily":        # 03:00 UTC, 300 results
    "fetch-semanticscholar-daily":  # 03:30 UTC, 200 results
    "fetch-biorxiv-weekly":         # Monday 04:00 UTC
}
```

Autodiscovery registers tasks from modules 1–4 (`module1_fetch`, `module1b_parse`, `module2_chunk`, `module3_embed`, `module4_index`).

---

## Configuration (`shared/config.py`)

Pydantic `BaseSettings` loaded from environment / `.env` file.

| Group | Key settings |
|-------|-------------|
| OpenRouter | `openrouter_api_key`, `openrouter_base_url` |
| NCBI / PubMed | `ncbi_api_key` |
| Semantic Scholar | `semantic_scholar_api_key` |
| Unpaywall | `unpaywall_email` |
| AWS | `aws_access_key_id`, `aws_secret_access_key`, `aws_region`, `s3_bucket` |
| PostgreSQL | `database_url` |
| Redis/RabbitMQ | `redis_url`, `amqp_url` |
| Qdrant | `qdrant_url`, `qdrant_api_key` |
| Grobid | `grobid_url` |
| MLflow | `mlflow_tracking_uri` |

---

## Data Models (`shared/models.py`)

### `Chunk`

Central unit of information flowing through embed → index → retrieve.

```python
class Chunk(BaseModel):
    chunk_id: UUID
    doi: str
    doi_slug: str          # filesystem-safe DOI

    # Bibliographic metadata
    title: str
    authors: list[str]
    journal: str
    pub_date: str          # YYYY-MM-DD
    pub_year: int
    source_db: str         # pubmed | europepmc | semanticscholar | biorxiv

    # Chunk position
    section_heading: str
    chunk_index: int
    sub_index: int
    element_type: str      # abstract | section | figure | table

    # Content
    mesh_terms: list[str]
    keywords: list[str]
    text: str
    text_with_header: str  # header-injected version for embedding

    # S3 back-reference
    s3_parsed_key: str

    # Flags
    has_figure: bool
    has_table: bool

    # Populated by Module 3
    dense_vector: list[float] | None
    sparse_indices: list[int] | None
    sparse_values: list[float] | None
```

---

## Database (`shared/db.py`)

SQLAlchemy engine with:

- **Pool size**: 10 connections, **max overflow**: 20 (30 total)
- **`pool_pre_ping=True`**: Recycles stale connections before use

```python
with get_session() as session:
    # auto-commit on __exit__, auto-rollback on exception
```

---

## S3 Client (`shared/s3.py`)

Thin boto3 wrapper. Key layout:

```
s3://bucket/
  raw/{source}/{paper_id}.{pdf|xml}     ← raw download
  parsed/{doi_slug}/
    structured.json                      ← full parsed document
    metadata.json
    figures/{fig_id}.png
    tables/table_{n}.md
  chunks/{doi_slug}.jsonl               ← one Chunk per line
```

| Function | Signature |
|----------|-----------|
| `upload` | `(key, data: bytes, content_type)` |
| `download` | `(key) -> bytes` |
| `exists` | `(key) -> bool` |
| `delete` | `(key)` |
| `list_keys` | `(prefix) -> list[str]` |

---

## Observability (`shared/observability.py`)

### Logging

Structlog with JSON output. Processors applied in order:

1. `contextvars` — propagate request-scoped context
2. `add_log_level`
3. `TimeStamper(fmt="iso")`
4. `StackInfoRenderer`
5. `JSONRenderer`

### Tracing

OpenTelemetry SDK, `BatchSpanProcessor`, service name `rag-medical`. OTLP export is optional (configured via `settings.otlp_endpoint`).

### Prometheus Metrics

All metrics are defined once and referenced across modules. Exposed on **`:8000/metrics`** via `start_metrics_server()`.

```python
papers_fetched_total        = Counter(labels=["source"])
papers_parsed_total         = Counter(labels=["status"])
chunks_indexed_total        = Counter()
embedding_latency_seconds   = Histogram()
retrieval_latency_seconds   = Histogram(labels=["strategy"])
rerank_latency_seconds      = Histogram()
agent_run_latency_seconds   = Histogram()
figure_describe_latency_seconds = Histogram()
openrouter_tokens_total     = Counter(labels=["model", "type"])
qdrant_points_total         = Gauge()
```

---

## Utilities (`shared/utils.py`)

| Function | Returns | Example |
|----------|---------|---------|
| `doi_to_slug(doi)` | URL/filesystem-safe string | `10.1234/abc` → `10-1234-abc` |
| `synthetic_key(title, author)` | SHA-256 hex prefix | Used when DOI is absent |
