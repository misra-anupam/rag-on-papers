# RAG on Papers — TODO

> Tracks every build task derived from `RAG_Project_Spec.md`.
> Work top-to-bottom: each phase unlocks the next.

---

## Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Done
- `[!]` Blocked

---

## Phase 1 — Infrastructure

### Repository scaffold
- [x] Create directory tree: `modules/`, `shared/`, `docker/`, `tests/`, `eval/`
- [x] Create `pyproject.toml` with all dependencies from spec
- [x] Create `.env.example` with all variables from spec env reference table
- [x] Create empty `README.md`

### Docker Compose
- [x] Write `docker/docker-compose.yml` — all 12 services:
  - [x] `rabbitmq` (rabbitmq:3-management, ports 5672 + 15672)
  - [x] `redis` (redis:7-alpine, port 6379)
  - [x] `postgres` (postgres:15, env vars, pg_data volume)
  - [x] `qdrant` (qdrant/qdrant:v1.9.0, port 6333, qdrant_data volume)
  - [x] `grobid` (lfoppiano/grobid:0.8.0, port 8070, 4 GB memory limit)
  - [x] `celery_worker` (build ., concurrency=4, depends on all services)
  - [x] `celery_beat` (build ., depends on rabbitmq/redis/postgres)
  - [x] `prometheus` (prom/prometheus, prometheus.yml volume mount)
  - [x] `grafana` (grafana/grafana, port 3000, grafana_data volume)
  - [x] `loki` (grafana/loki:2.9.0, port 3100)
  - [x] `promtail` (grafana/promtail:2.9.0, log + config volume mounts)
- [x] Write `docker/prometheus.yml` — scrape config
- [x] Write `docker/promtail-config.yml` — Loki forwarding config
- [ ] `docker-compose up` — all services healthy

### Shared infrastructure code
- [x] `shared/config.py` — Pydantic Settings loading all env vars
- [x] `shared/celery_app.py` — Celery app instance (broker, backend, serializer)
- [x] `shared/db.py` — SQLAlchemy session factory (DATABASE_URL)
- [x] `shared/s3.py` — boto3 S3 wrapper (`upload(bytes, key)`, `download(key)`)
- [x] `shared/observability.py` — structlog + OTel initialisation (see Module X)
- [x] `shared/models.py` — `Chunk` Pydantic model (all fields from §2.5)

### Database
- [x] Write `shared/migrations/001_paper_registry.sql` — `paper_registry` table + all indexes
- [ ] Run migration against Postgres container — schema applied cleanly
- [ ] Verify all six indexes created (`fetch_status`, `parse_status`, `embed_status`, `publication_date`, `source`, synthetic-key note)

### Qdrant collection
- [x] Write `modules/module4_index/setup.py` — `create_collection()` (dense HNSW + sparse SPLADE config)
- [x] Create payload indexes for all 9 fields (doi, pub_year, pub_date, element_type, mesh_terms, journal, source_db, has_figure, has_table)
- [ ] Run `create_collection()` — collection visible in Qdrant dashboard

**Phase 1 acceptance:** `docker-compose up` healthy, Qdrant collection created, Postgres schema migrated.

---

## Phase 2 — Module 1: Fetch, Deduplicate, Store

### Celery Beat schedule
- [x] Beat schedule wired into `shared/celery_app.py` (4 jobs: pubmed/europepmc/semanticscholar/biorxiv)

### Source adapters — shared base
- [x] `modules/module1_fetch/adapters/base.py` — `BaseAdapter` ABC, `RateLimiter`, `make_retry` decorator
- [x] httpx.AsyncClient + tenacity retry (exponential backoff, max 5, jitter)

### PubMed Central adapter
- [x] `modules/module1_fetch/adapters/pubmed.py` — search (esearch) + fetch (efetch) + DOI extraction + 10/3 req/s rate limit

### Europe PMC adapter
- [x] `modules/module1_fetch/adapters/europepmc.py` — search + fetch (PDF or JSON fallback)

### Semantic Scholar adapter
- [x] `modules/module1_fetch/adapters/semanticscholar.py` — search + fetch (openAccessPdf or Unpaywall fallback)

### bioRxiv / medRxiv adapter
- [x] `modules/module1_fetch/adapters/biorxiv.py` — last 7 days, both servers, DOI-based fetch

### Unpaywall fallback
- [x] `modules/module1_fetch/adapters/unpaywall.py` — `resolve(doi) -> str | None`

### Deduplication registry
- [x] `modules/module1_fetch/registry.py` — `exists()`, `upsert()`, `update()` via SQLAlchemy text queries

### Celery tasks
- [x] `modules/module1_fetch/tasks.py` — all 4 batch tasks + `fetch_single_paper` with full retry config

### Tests — Module 1
- [x] `tests/module1/test_adapters.py`
- [x] `tests/module1/test_dedup.py`
- [x] `tests/module1/test_tasks.py`

**Phase 2 acceptance:** All four source adapters fetch papers, S3 uploads verified, Postgres registry rows inserted, Celery Beat dispatches on schedule.

---

## Phase 3 — Module 1b: PDF / XML Parsing

### Grobid client
- [x] `modules/module1b_parse/grobid_client.py` — direct HTTP POST to `/api/processFulltextDocument` with all required params
- [x] `modules/module1b_parse/grobid_config.json` — points to `http://grobid:8070`

### TEI XML parser (lxml)
- [x] `modules/module1b_parse/tei_parser.py` — `parse_tei()`, all sub-extractors, `_parse_coords()` for Grobid bboxes

### PMC XML parser (lxml)
- [x] `modules/module1b_parse/pmc_parser.py` — `parse_pmc_xml()`, schema identical to TEI parser output

### Figure handler
- [x] `modules/module1b_parse/figure_handler.py` — PyMuPDF crop + S3 upload + OpenRouter gpt-4o description

### Table handler
- [x] `modules/module1b_parse/table_handler.py` — `save_table_to_s3()`

### Parse Celery task
- [x] `modules/module1b_parse/tasks.py` — `parse_paper` task with XML/PDF branching, structured.json + metadata.json upload, registry update, chain to Module 2

### Tests — Module 1b
- [x] `tests/module1b/test_tei_parser.py`
- [x] `tests/module1b/test_pmc_parser.py`
- [x] `tests/module1b/test_figure_handler.py`
- [x] `tests/module1b/test_table_handler.py`

**Phase 3 acceptance:** Grobid parses 5 test PDFs, `structured.json` matches schema, figure PNGs uploaded to S3, LLM descriptions generated and stored.

---

## Phase 4 — Module 2: Context-Aware Chunking

- [x] `modules/module2_chunk/chunker.py` — tiktoken cl100k_base, RecursiveCharacterTextSplitter, all 4 chunk types, `chunk_paper()`, JSONL save/load
- [x] `modules/module2_chunk/header.py` — `inject_header()` with Paper/Journal/Section/--- format
- [x] `modules/module2_chunk/tasks.py` — `chunk_paper` Celery task, chains to Module 3
- [x] `tests/module2/test_chunker.py`
- [x] `tests/module2/test_header.py`
- [x] `tests/module2/test_chunk_types.py`

**Phase 4 acceptance:** Chunks produced for 3 papers, metadata schema matches `Chunk` model, header injection verified, no chunk exceeds 512 tokens.

---

## Phase 5 — Module 3: Tokenisation and Embedding

- [x] `modules/module3_embed/dense.py` — async batched embedding, 512d Matryoshka, semaphore=5, tenacity retry
- [x] `modules/module3_embed/sparse.py` — FastEmbed SPLADE_PP_en_v1, lru_cache model, CPU-only
- [x] `modules/module3_embed/tasks.py` — `embed_chunks` Celery task, chains to Module 4
- [x] `tests/module3/test_dense.py`
- [x] `tests/module3/test_sparse.py`
- [x] `tests/module3/test_embed_task.py`

**Phase 5 acceptance:** Dense vectors shape `(512,)`, sparse vectors non-empty, end-to-end embedding for 1 paper completes without error.

---

## Phase 6 — Module 4: Vector Store Ingestion

- [x] `modules/module4_index/setup.py` — idempotent `create_collection()`, all 9 payload indexes (Phase 1)
- [x] `modules/module4_index/ingest.py` — `ingest_chunks()`, `delete_paper()`, `fetch_vectors_from_qdrant()`
- [x] `modules/module4_index/tasks.py` — `ingest_to_qdrant` Celery task
- [x] `tests/module4/test_ingest.py` — upsert, idempotency, skip-no-vector, delete
- [ ] `tests/module4/test_delete.py` — (covered in test_ingest.py `test_delete_paper`)
- [ ] Run `create_collection()` — collection visible in Qdrant dashboard

**Phase 6 acceptance:** Qdrant collection point count matches chunk count, payload indexes confirmed, upsert re-run is idempotent.

---

## Phase 7 — Module 5: Retrieval Pipeline

- [x] `modules/module5_retrieve/base.py` — `RetrievalResult` dataclass + `BaseRetriever` ABC
- [x] `modules/module5_retrieve/tag.py` — `build_filter()` handling all 5 filter types
- [x] `modules/module5_retrieve/semantic.py` — `SemanticRetriever`
- [x] `modules/module5_retrieve/lexical.py` — `LexicalRetriever`
- [x] `modules/module5_retrieve/hybrid.py` — `HybridRetriever` with Qdrant-native RRF
- [x] `modules/module5_retrieve/__init__.py` — `get_retriever()` factory
- [x] `tests/module5/test_retrievers.py`
- [x] `tests/module5/test_filter.py`

**Phase 7 acceptance:** All four retrievers return top-100 results for 3 test queries; tag filter correctly restricts results; interface contract enforced.

---

## Phase 8 — Module 6: Reranking Pipeline

- [x] `modules/module6_rerank/rrf.py` — `reciprocal_rank_fusion()` with k=60
- [x] `modules/module6_rerank/mmr.py` — `cosine_sim()` + `max_marginal_relevance()` with lambda=0.7
- [x] `modules/module6_rerank/pipeline.py` — `rerank()` two-stage (RRF → MMR), vector fetch from Qdrant
- [x] `tests/module6/test_rrf.py`
- [x] `tests/module6/test_mmr.py`
- [x] `tests/module6/test_pipeline.py`

**Phase 8 acceptance:** RRF fuses semantic + lexical lists correctly; MMR output is demonstrably more diverse than top-8 by score alone.

---

## Phase 9 — Module 7: RAG Agent (CrewAI)

- [x] `modules/module7_agent/tools.py` — `retrieve_tool`, `multi_hop_retrieve_tool`, `_generate_followup_query`, `format_chunks_for_agent`
- [x] `modules/module7_agent/crew.py` — 3 agents (retrieval/analysis/synthesis), 3 tasks, `run_query()`, Prometheus latency tracking
- [ ] `tests/module7/test_tools.py` — mock retriever + reranker (requires live Qdrant for integration)
- [ ] `tests/module7/test_crew.py` — integration test requiring live LLM (manual run)

**Phase 9 acceptance:** Full crew run on 5 queries; citations present in all outputs; multi-hop tool triggered on a chained question.

---

## Phase 10 — Module 8: Evaluation Framework

- [x] `eval/eval_set.jsonl` — 10 seed queries (4 types: factual/comparative/multi-hop/broad); grow to 200
- [x] `modules/module8_eval/retrieval_metrics.py` — `recall_at_k`, `mean_reciprocal_rank`, `mean_recall_at_k`, `mean_mrr`
- [x] `modules/module8_eval/ragas_eval.py` — `evaluate_strategy()` with 4 RAGAS metrics
- [x] `modules/module8_eval/ablation.py` — `run_ablation()` with MLflow logging
- [ ] Grow `eval/eval_set.jsonl` to 200 queries
- [ ] Run ablation after corpus is populated — verify RAGAS targets met

**Phase 10 acceptance:** RAGAS scores computed for all strategies; MLflow experiment logged; ablation table readable in MLflow UI.

---

## Phase 11 — Observability (Module X, Cross-Cutting)

### structlog + OTel (shared/observability.py — DONE in Phase 1)
- [x] structlog configured (merge_contextvars, add_log_level, TimeStamper, JSONRenderer)
- [x] OTel tracer setup with OTLP exporter + `configure_tracing()`
- [x] All 10 Prometheus metrics defined

### Instrumentation in modules
- [x] `papers_fetched_total` — Module 1 `fetch_single_paper`
- [x] `papers_parsed_total` — Module 1b `parse_paper`
- [x] `chunks_indexed_total` + `qdrant_points_total` — Module 4 `ingest_chunks`
- [x] `embedding_latency_seconds` — Module 3 `dense.py`
- [x] `retrieval_latency_seconds` (by strategy) — Module 5 all retrievers
- [x] `rerank_latency_seconds` — Module 6 `pipeline.py`
- [x] `agent_run_latency_seconds` — Module 7 `crew.py`
- [x] `figure_describe_latency_seconds` — Module 1b `figure_handler.py`
- [x] `log.info` / `log.error` in all task files
- [ ] Expose `/metrics` HTTP endpoint from Celery worker process
- [ ] OTel span instrumentation inside individual functions (key spans listed in spec)

### Grafana dashboards
- [ ] Verify Loki datasource receives JSON logs
- [ ] Verify Prometheus datasource scrapes metrics
- [ ] Build 5 dashboards (ingest/parse/embed/retrieval/collection-size)
- [ ] Verify OTel spans visible

**Phase 11 acceptance:** JSON logs flowing to Loki; OTel spans visible in Grafana; Prometheus metrics scraped; key dashboards built.

---

## Ongoing / Cross-Cutting

- [ ] `tests/` — maintain ≥80% coverage across all modules
- [ ] CI config (GitHub Actions or equivalent) — lint, type-check, unit tests on every push
- [ ] `eval/eval_set.jsonl` — grow to 200 queries covering all query types
- [ ] Review RAGAS targets quarterly; adjust retrieval params if below threshold
- [ ] Rotate `OPENROUTER_API_KEY` and other secrets per security policy
- [ ] Qdrant snapshot before any bulk re-index or embedding model upgrade
