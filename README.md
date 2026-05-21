# RAG on Papers

Production-grade Retrieval-Augmented Generation system for medical research papers.

Ingests from PubMed Central, Europe PMC, Semantic Scholar, and bioRxiv/medRxiv. Parses with Grobid. Embeds with dense (OpenRouter text-embedding-3-large, 512d Matryoshka) and sparse (FastEmbed SPLADE) vectors. Stores in Qdrant. Answers queries via a three-agent CrewAI crew with full inline citations.

## Quick start

```bash
cp .env.example .env
# fill in API keys

cd docker
docker-compose up -d
```

Run the Qdrant collection setup:

```bash
python -m modules.module4_index.setup
```

## Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Broker / Queue | RabbitMQ + Celery 5 + Celery Beat |
| Database | PostgreSQL 15 |
| Object store | AWS S3 |
| PDF parser | Grobid 0.8 |
| Vector store | Qdrant (HNSW + sparse vectors) |
| Embeddings | OpenRouter text-embedding-3-large (512d) |
| Sparse encoding | FastEmbed SPLADE_PP_en_v1 |
| LLM / Agent | OpenRouter + CrewAI |
| Evaluation | RAGAS + MLflow |
| Observability | structlog + OTel + Prometheus + Grafana + Loki |

## Module map

| # | Module | Purpose |
|---|---|---|
| 1 | `module1_fetch` | Fetch, deduplicate, store papers |
| 1b | `module1b_parse` | Grobid PDF/XML parsing, figure + table extraction |
| 2 | `module2_chunk` | Context-aware chunking with header injection |
| 3 | `module3_embed` | Dense + sparse embedding |
| 4 | `module4_index` | Qdrant ingestion |
| 5 | `module5_retrieve` | Retrieval strategies (semantic, lexical, hybrid, tag) |
| 6 | `module6_rerank` | RRF + MMR reranking |
| 7 | `module7_agent` | CrewAI RAG agent |
| 8 | `module8_eval` | RAGAS evaluation + MLflow ablation |
