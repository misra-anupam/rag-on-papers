# RAG on Papers

Production-grade Retrieval-Augmented Generation system for medical research papers. Continuously ingests from PubMed, Europe PMC, Semantic Scholar, bioRxiv/medRxiv; parses PDFs and JATS XML; chunks, embeds (dense + sparse), and indexes into Qdrant; then serves hybrid search with a multi-agent CrewAI answer layer.

## Full Pipeline

```mermaid
flowchart TD
    subgraph Ingest ["Nightly Ingest (Celery Beat)"]
        B1[fetch_pubmed_batch\n02:00 UTC · 500 papers]
        B2[fetch_europepmc_batch\n03:00 UTC · 300 papers]
        B3[fetch_semantic_scholar_batch\n03:30 UTC · 200 papers]
        B4[fetch_biorxiv_batch\nMonday 04:00 UTC]
    end

    B1 & B2 & B3 & B4 --> FSP

    subgraph M1 ["Module 1 — Fetch"]
        FSP[fetch_single_paper\nRate-limited · Retryable · Dedup]
        S3R[(S3\nraw/)]
        REG[(PostgreSQL\npaper_registry)]
        FSP --> S3R
        FSP --> REG
    end

    FSP -->|parse_paper.delay| M1B

    subgraph M1B ["Module 1b — Parse"]
        PP[parse_paper]
        GRO[Grobid\nPDF → TEI XML]
        PMC[pmc_parser\nJATS XML]
        FIG[figure_handler\nPyMuPDF + GPT-4o vision]
        S3P[(S3\nparsed/)]
        PP --> GRO & PMC
        PP --> FIG --> S3P
        PP --> S3P
    end

    M1B -->|chunk_paper.delay| M2

    subgraph M2 ["Module 2 — Chunk"]
        CP[chunk_paper\n512 tok · 80 overlap]
        S3C[(S3\nchunks/)]
        CP --> S3C
    end

    M2 -->|embed_chunks.delay| M3

    subgraph M3 ["Module 3 — Embed"]
        EC[embed_chunks]
        DE[dense\ntext-embedding-3-large\nbatch=100 · concurrency=5]
        SP[sparse\nSPLADE_PP_en_v1]
        EC --> DE & SP
    end

    M3 -->|ingest_to_qdrant.delay| M4

    subgraph M4 ["Module 4 — Index"]
        IQ[ingest_to_qdrant\nHNSW · INT8 quant]
        QD[(Qdrant\nmedical_papers)]
        IQ --> QD
    end

    subgraph Query ["Query Time"]
        UQ([User Query])
        UQ --> AG

        subgraph M7 ["Module 7 — Agent"]
            AG[CrewAI\n3 Agents · Sequential]
        end

        AG --> M5

        subgraph M5 ["Module 5 — Retrieve"]
            RET[Semantic / Lexical / Hybrid]
        end

        M5 --> M6

        subgraph M6 ["Module 6 — Rerank"]
            RRF[RRF Fusion]
            MMR[MMR Diversity]
            RRF --> MMR
        end

        M6 --> AG
        AG --> ANS([Answer + Citations])
    end

    QD --> RET
```

## Module Summary

| Module | Entrypoint | Technology | Output |
|--------|-----------|-----------|--------|
| [1 — Fetch](modules/module1-fetch.md) | `fetch_*_batch` / `fetch_single_paper` | httpx, asyncio, RateLimiter | Raw PDF/XML on S3, registry row |
| [1b — Parse](modules/module1b-parse.md) | `parse_paper` | Grobid, PyMuPDF, OpenRouter GPT-4o | Structured JSON on S3 |
| [2 — Chunk](modules/module2-chunk.md) | `chunk_paper` | langchain-text-splitters, tiktoken | JSONL of chunks on S3 |
| [3 — Embed](modules/module3-embed.md) | `embed_chunks` | OpenRouter text-embedding-3-large, SPLADE_PP | Chunks with dense + sparse vectors |
| [4 — Index](modules/module4-index.md) | `ingest_to_qdrant` | Qdrant (HNSW + scalar quant) | Indexed points in Qdrant |
| [5 — Retrieve](modules/module5-retrieve.md) | `get_retriever(strategy)` | Qdrant semantic/lexical/hybrid | `RetrievalResult[]` |
| [6 — Rerank](modules/module6-rerank.md) | `rerank()` | RRF + MMR | Diverse top-k results |
| [7 — Agent](modules/module7-agent.md) | `run_query()` | CrewAI, OpenRouter GPT-4o | Final answer with citations |
| [8 — Eval](modules/module8-eval.md) | `run_ablation()` | RAGAS, MLflow | Metrics by strategy |

## Observability at a Glance

All metrics are exposed via Prometheus on **port 8000**. Logs are structured JSON via structlog. Traces are emitted via OpenTelemetry (optional OTLP export).

| Metric | Type | Labels |
|--------|------|--------|
| `papers_fetched_total` | Counter | `source` |
| `papers_parsed_total` | Counter | `status` |
| `chunks_indexed_total` | Counter | — |
| `embedding_latency_seconds` | Histogram | — |
| `retrieval_latency_seconds` | Histogram | `strategy` |
| `rerank_latency_seconds` | Histogram | — |
| `agent_run_latency_seconds` | Histogram | — |
| `figure_describe_latency_seconds` | Histogram | — |
| `openrouter_tokens_total` | Counter | `model`, `type` |
| `qdrant_points_total` | Gauge | — |
