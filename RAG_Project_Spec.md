# Medical Research RAG System — Complete Project Specification
> For Claude Code — Module-by-Module Build Reference

---

## Stack at a Glance

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Broker / Queue | RabbitMQ + Celery 5 + Celery Beat |
| Database | PostgreSQL 15 — paper registry + metadata |
| Object store | AWS S3 |
| PDF parser | Grobid 0.8 (Docker, self-hosted) |
| Parsing fallback | PyMuPDF for non-Grobid PDFs |
| Figure handling | PyMuPDF crop + OpenRouter multimodal LLM |
| Vector store | Qdrant (HNSW + sparse vectors) |
| Embeddings | OpenRouter /v1/embeddings — text-embedding-3-large (512d Matryoshka) |
| Sparse encoding | FastEmbed — SPLADE_PP_en_v1 (local, no API) |
| LLM / Agent | OpenRouter /v1/chat/completions + CrewAI |
| Evaluation | RAGAS + MLflow |
| Observability | structlog + OpenTelemetry + Prometheus + Grafana + Loki |

---

## 0. Project Overview

This project is a production-grade Retrieval-Augmented Generation (RAG) system for medical research papers. It ingests papers from four public APIs, parses them with Grobid, produces context-aware chunks, embeds them with dense and sparse vectors, and stores everything in Qdrant. A three-agent CrewAI crew then answers user queries with full inline citations.

### 0.1 Module Map

| # | Module | Primary technologies |
|---|---|---|
| 1 | Fetch, deduplicate, store | Celery Beat · httpx · boto3 · PostgreSQL |
| 1b | PDF / XML parsing | Grobid · lxml · PyMuPDF · OpenRouter multimodal |
| 2 | Context-aware chunking | tiktoken · LangChain splitters · custom Python |
| 3 | Tokenisation + embedding | tiktoken · OpenRouter embeddings · FastEmbed SPLADE |
| 4 | Vector store ingestion | Qdrant · qdrant-client |
| 5 | Retrieval pipeline | Qdrant hybrid search · semantic · lexical · tag |
| 6 | Reranking pipeline | RRF (custom Python) · MMR (custom Python) |
| 7 | RAG agent | CrewAI · OpenRouter LLM |
| 8 | Evaluation framework | RAGAS · MLflow |
| X | Observability (cross-cutting) | structlog · OTel · Prometheus · Grafana · Loki |

### 0.2 Repository Layout

```
rag-medical/
  modules/
    module1_fetch/         # Celery tasks, source adapters
    module1b_parse/        # Grobid client, TEI parser, figure/table handlers
    module2_chunk/         # Chunking strategies, header injection
    module3_embed/         # Tokenisation, dense + sparse embedding
    module4_index/         # Qdrant collection setup, upsert, management
    module5_retrieve/      # Retrieval strategies — abstract interface
    module6_rerank/        # RRF + MMR implementations
    module7_agent/         # CrewAI crew, agents, tools, prompts
    module8_eval/          # RAGAS eval harness, MLflow logging
  shared/
    config.py              # Pydantic settings loaded from env
    models.py              # Shared Pydantic data models (Chunk, Paper...)
    celery_app.py          # Celery application instance
    db.py                  # SQLAlchemy session factory
    s3.py                  # S3 client wrapper (upload/download)
    observability.py       # OTel + structlog initialisation
  docker/
    docker-compose.yml     # All services: Grobid, Qdrant, RabbitMQ, Postgres,
                           #   Redis, Prometheus, Grafana, Loki, Promtail
  tests/
    module1/  module2/  ...  # Per-module unit + integration tests
  eval/
    eval_set.jsonl         # Test queries with ground-truth answers + source DOIs
  .env.example
  pyproject.toml
  README.md
```

---

## Module 1 — Fetch, Deduplicate, Store

Periodically fetches research papers from four public APIs (PubMed Central, Europe PMC, Semantic Scholar, bioRxiv/medRxiv). Deduplicates by DOI against a PostgreSQL registry. Stores raw artefacts in S3. Chains to Module 1b on success.

### 1.1 Celery Beat Schedule

Celery Beat runs as a separate process alongside Celery workers. It dispatches one lightweight "batch" task per source on the configured cron. Each batch task fans out individual paper-fetch tasks onto the default queue for parallel worker execution — Beat itself never does I/O.

```python
# modules/module1_fetch/schedule.py
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'fetch-pubmed-daily': {
        'task':     'module1_fetch.tasks.fetch_pubmed_batch',
        'schedule': crontab(hour=2, minute=0),
        'kwargs':   {'query': 'metformin OR diabetes OR renal', 'max_results': 500}
    },
    'fetch-europepmc-daily': {
        'task':     'module1_fetch.tasks.fetch_europepmc_batch',
        'schedule': crontab(hour=3, minute=0),
        'kwargs':   {'query': 'clinical pharmacology adverse effects', 'max_results': 300}
    },
    'fetch-semanticscholar-daily': {
        'task':     'module1_fetch.tasks.fetch_semantic_scholar_batch',
        'schedule': crontab(hour=3, minute=30),
        'kwargs':   {'query': 'drug mechanism clinical trial', 'max_results': 200}
    },
    'fetch-biorxiv-weekly': {
        'task':     'module1_fetch.tasks.fetch_biorxiv_batch',
        'schedule': crontab(day_of_week=1, hour=4, minute=0)
    },
}

CELERY_BROKER_URL      = 'amqp://guest:guest@rabbitmq:5672//'
CELERY_RESULT_BACKEND  = 'redis://redis:6379/0'
CELERY_TASK_SERIALIZER = 'json'
```

### 1.2 Source Adapters

Each source implements a two-method interface: `search(query, max) -> list[str]` returning IDs, and `fetch(id) -> bytes` returning the raw file. All HTTP calls use `httpx.AsyncClient` with tenacity retry (exponential backoff, max 5 retries, jitter).

#### PubMed Central (PMC)

```
Endpoints:
  esearch: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
           ?db=pmc&term={query}&retmax={n}&retmode=json&api_key={key}
  efetch:  https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
           ?db=pmc&id={pmcid}&rettype=xml&retmode=xml&api_key={key}

Rate limits: 3 req/s without key, 10 req/s with NCBI_API_KEY
Returns:     full-text TEI-compatible XML
S3 path:     s3://{BUCKET}/raw/pubmed/{pmcid}.xml
Dedup key:   DOI extracted from XML header
```

#### Europe PMC

```
Endpoint:
  https://www.ebi.ac.uk/europepmc/webservices/rest/search
  ?query={query}&format=json&pageSize={n}&resultType=core

Returns:  JSON with abstract, DOI, open-access PDF URL (externalLinks)
Download: PDF if externalLinks[].availableUrl == true
S3 path:  s3://{BUCKET}/raw/europepmc/{accession}.pdf  (or .json if no PDF)
No API key required
```

#### Semantic Scholar

```
Endpoint:
  https://api.semanticscholar.org/graph/v1/paper/search
  ?query={query}&fields=paperId,title,authors,year,doi,
         isOpenAccess,openAccessPdf,abstract&limit={n}

Rate limits: 100 req/5min unauthed, higher with SEMANTIC_SCHOLAR_API_KEY
PDF URL:     openAccessPdf.url if present; else Unpaywall fallback
S3 path:     s3://{BUCKET}/raw/semanticscholar/{paper_id}.pdf
```

#### bioRxiv / medRxiv

```
Endpoint:
  https://api.biorxiv.org/details/{server}/{start_date}/{end_date}/json
  server = biorxiv | medrxiv

Weekly fetch: last 7 days of new preprints
PDF URL:      https://www.biorxiv.org/content/{doi}.full.pdf
S3 path:      s3://{BUCKET}/raw/biorxiv/{doi_slug}.pdf
```

#### Unpaywall (PDF resolution fallback)

```
Used when Semantic Scholar / Europe PMC lack a direct PDF URL
Endpoint: https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}
Returns:  oa_locations[].url_for_pdf — download if not null
Required env: UNPAYWALL_EMAIL
```

### 1.3 Celery Task Pattern

```python
# modules/module1_fetch/tasks.py

@celery_app.task(bind=True, max_retries=3)
def fetch_pubmed_batch(self, query: str, max_results: int):
    pmcids = pubmed_adapter.search(query, max_results)
    for pmcid in pmcids:
        fetch_single_paper.delay(source='pubmed', paper_id=pmcid)


@celery_app.task(
    bind=True,
    max_retries=5,
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def fetch_single_paper(self, source: str, paper_id: str):
    doi = resolve_doi(source, paper_id)           # source-specific DOI lookup
    if doi and doi_registry.exists(doi):           # dedup check
        return

    raw_bytes = adapters[source].fetch(paper_id)  # httpx download
    ext       = 'xml' if source == 'pubmed' else 'pdf'
    s3_key    = f'raw/{source}/{paper_id}.{ext}'
    s3.upload(raw_bytes, key=s3_key)

    doi_registry.upsert(
        doi=doi, source=source, paper_id=paper_id,
        s3_raw_key=s3_key, fetch_status='fetched'
    )
    parse_paper.delay(                             # chain to Module 1b
        source=source, paper_id=paper_id, s3_key=s3_key
    )
```

### 1.4 Deduplication Registry (PostgreSQL)

```sql
-- shared/migrations/001_paper_registry.sql

CREATE TABLE paper_registry (
    doi              TEXT PRIMARY KEY,
    paper_id         TEXT,                 -- source-native ID
    source           TEXT        NOT NULL, -- pubmed|europepmc|semanticscholar|biorxiv
    fetch_status     TEXT        NOT NULL DEFAULT 'fetched',
    parse_status     TEXT        NOT NULL DEFAULT 'pending',
    embed_status     TEXT        NOT NULL DEFAULT 'pending',
    index_status     TEXT        NOT NULL DEFAULT 'pending',
    title            TEXT,
    authors          JSONB,
    journal          TEXT,
    publication_date DATE,
    mesh_terms       TEXT[],
    s3_raw_key       TEXT,
    s3_parsed_key    TEXT,
    fetched_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON paper_registry (fetch_status);
CREATE INDEX ON paper_registry (parse_status);
CREATE INDEX ON paper_registry (embed_status);
CREATE INDEX ON paper_registry (publication_date);
CREATE INDEX ON paper_registry (source);

-- Papers without DOIs: use SHA256(title || first_author) as synthetic key
```

### 1.5 S3 Layout

```
s3://{BUCKET}/
  raw/
    pubmed/{pmcid}.xml
    semanticscholar/{paper_id}.pdf
    europepmc/{accession}.pdf
    biorxiv/{doi_slug}.pdf
  parsed/
    {doi_slug}/
      structured.json          # full Grobid/lxml output (see Module 1b schema)
      metadata.json            # doi, title, authors, mesh_terms, journal, date
      figures/
        fig_{n}.png            # cropped PNG from PDF page
        fig_{n}_desc.txt       # LLM-generated textual description
      tables/
        table_{n}.md           # markdown table
  chunks/
    {doi_slug}.jsonl           # one JSON object per line, all chunks for paper
```

### 1.6 Module 1 Environment Variables

| Variable | Purpose |
|---|---|
| `NCBI_API_KEY` | PMC rate limit: 3 → 10 req/s |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar rate limit increase |
| `UNPAYWALL_EMAIL` | Required parameter by Unpaywall API |
| `AWS_BUCKET_NAME` | S3 bucket for all raw and parsed artefacts |
| `AWS_ACCESS_KEY_ID` | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `AWS_REGION` | AWS region (e.g. us-east-1) |
| `DATABASE_URL` | PostgreSQL connection string |
| `CELERY_BROKER_URL` | RabbitMQ amqp:// connection string |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery task results |

---

## Module 1b — PDF / XML Parsing

Converts raw S3 artefacts into structured JSON. Grobid handles all PDFs. lxml handles PMC XML directly. Figures are extracted as PNG crops and described by an OpenRouter multimodal LLM. Tables are converted to Markdown. Triggers Module 2 on completion.

### 1b.1 Grobid — Setup and Configuration

Grobid runs as a Docker service. The `grobid-client-python` library communicates with it over HTTP. Grobid is purpose-built for scientific paper parsing and handles two-column layouts, reference extraction, and section segmentation far better than general PDF parsers.

```yaml
# docker/docker-compose.yml — Grobid service
grobid:
  image: lfoppiano/grobid:0.8.0
  ports: ['8070:8070']
  environment:
    - GROBID_MAX_CONNECTIONS=10
  deploy:
    resources:
      limits:
        memory: 4G
```

```python
# modules/module1b_parse/grobid_client.py
# pip install grobid-client-python
from grobid_client.grobid_client import GrobidClient

client = GrobidClient(config_path='grobid_config.json')
# grobid_config.json must point grobidServerURL to http://grobid:8070

def parse_pdf_to_tei(pdf_path: str) -> str:
    result = client.process_pdf(
        'processFulltextDocument',
        pdf_path,
        generateIDs=True,
        consolidate_header=True,
        consolidate_citations=False,   # not needed for RAG — saves time
        tei_coordinates=True,          # REQUIRED for figure bbox extraction
        segment_sentences=True,
    )
    return result   # TEI XML string
```

### 1b.2 Structured JSON Output Schema

Both the Grobid TEI parser and the lxml PMC XML parser emit this same schema. Downstream modules only consume `structured.json` — they never touch raw PDFs or XML.

```python
# s3://parsed/{doi_slug}/structured.json
{
  'doi':      str,
  'title':    str,
  'abstract': str,
  'authors':  [{'name': str, 'affiliation': str}],
  'journal':  str,
  'pub_date': str,      # ISO date YYYY-MM-DD
  'mesh_terms':  [str], # from PMC XML or Grobid header
  'keywords':    [str],
  'sections': [
    {
      'heading':     str,
      'text':        str,      # full section text
      'figure_refs': [str],    # fig IDs referenced in this section
      'table_refs':  [str],
    }
  ],
  'figures': [
    {
      'fig_id':      str,
      'caption':     str,
      'coords':      {'page': int, 'x': float, 'y': float,
                      'w': float, 'h': float},
      's3_img_key':  str,   # cropped PNG
      'description': str,   # LLM-generated
    }
  ],
  'tables': [
    {
      'table_id': str,
      'caption':  str,
      'markdown': str,      # table as markdown
    }
  ],
}
```

### 1b.3 TEI XML Parsing (lxml)

```python
# modules/module1b_parse/tei_parser.py
from lxml import etree

NS = {'tei': 'http://www.tei-c.org/ns/1.0'}

def parse_tei(tei_xml: str) -> dict:
    root = etree.fromstring(tei_xml.encode())
    return {
        'title':    root.findtext('.//tei:titleStmt/tei:title', namespaces=NS),
        'abstract': ' '.join(p.text or '' for p in
                    root.findall('.//tei:abstract//tei:p', namespaces=NS)),
        'authors':  _extract_authors(root),
        'sections': _extract_sections(root),
        'figures':  _extract_figure_refs(root),
        'tables':   _extract_tables(root),
        'keywords': [k.text for k in
                    root.findall('.//tei:keywords/tei:term', namespaces=NS)],
    }

def _extract_sections(root) -> list:
    sections = []
    for div in root.findall('.//tei:body/tei:div', namespaces=NS):
        heading  = div.findtext('tei:head', namespaces=NS, default='')
        paras    = [p.text or '' for p in div.findall('tei:p', namespaces=NS)]
        fig_refs = [r.get('target', '').lstrip('#')
                   for r in div.findall('.//tei:ref[@type="figure"]',
                   namespaces=NS)]
        sections.append({
            'heading':     heading,
            'text':        '\n\n'.join(paras),
            'figure_refs': fig_refs,
            'table_refs':  [],
        })
    return sections
```

### 1b.4 Figure Handling — Option B (Crop + LLM Description)

For each figure: PyMuPDF crops the image region using Grobid's bounding box coordinates, uploads the PNG to S3, then sends it to an OpenRouter multimodal LLM with the caption for a 2–4 sentence clinical description. The description is stored as text and becomes a retrievable chunk in Module 2.

```python
# modules/module1b_parse/figure_handler.py
import fitz   # PyMuPDF — pip install pymupdf
import httpx, base64

def extract_and_describe_figure(
    pdf_path: str, fig: dict, doi_slug: str
) -> dict:

    # Step 1: Crop figure region
    doc  = fitz.open(pdf_path)
    page = doc[fig['coords']['page'] - 1]
    clip = fitz.Rect(
        fig['coords']['x'],
        fig['coords']['y'],
        fig['coords']['x'] + fig['coords']['w'],
        fig['coords']['y'] + fig['coords']['h'],
    )
    pix       = page.get_pixmap(clip=clip, dpi=150)
    img_bytes = pix.tobytes('png')

    # Step 2: Upload crop to S3
    s3_key = f'parsed/{doi_slug}/figures/{fig["fig_id"]}.png'
    s3.upload(img_bytes, key=s3_key, content_type='image/png')

    # Step 3: LLM description via OpenRouter
    b64 = base64.b64encode(img_bytes).decode()
    resp = httpx.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
        json={
            'model': 'openai/gpt-4o',
            'max_tokens': 400,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image_url',
                     'image_url': {'url': f'data:image/png;base64,{b64}'}},
                    {'type': 'text', 'text': (
                        'This figure is from a medical research paper. '
                        f'Caption: "{fig["caption"]}". '
                        'Describe what this figure shows in 2-4 sentences, '
                        'focusing on data, trends, and clinical significance.'
                    )}
                ]
            }]
        },
        timeout=30.0
    )
    description = resp.json()['choices'][0]['message']['content']

    # Step 4: Save description to S3
    s3.upload(description.encode(), key=s3_key.replace('.png', '_desc.txt'))
    return {**fig, 's3_img_key': s3_key, 'description': description}
```

### 1b.5 Table Handling

```python
# modules/module1b_parse/table_handler.py

def table_xml_to_markdown(table_elem, ns: dict) -> str:
    rows    = table_elem.findall('.//tei:row', namespaces=ns)
    md_rows = []
    for i, row in enumerate(rows):
        cells = [c.text_content().strip()
                 for c in row.findall('tei:cell', namespaces=ns)]
        md_rows.append('| ' + ' | '.join(cells) + ' |')
        if i == 0:   # header separator
            md_rows.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')
    return '\n'.join(md_rows)

# Tables stored as:
#   s3://parsed/{doi_slug}/tables/table_{n}.md
#   Also inlined into structured.json under tables[].markdown
#
# Chunking rule (Module 2): each table = one dedicated chunk.
# Never split a table across chunk boundaries.
```

### 1b.6 Parse Celery Task

```python
# modules/module1b_parse/tasks.py

@celery_app.task(bind=True, max_retries=3,
                 autoretry_for=(Exception,), retry_backoff=True)
def parse_paper(self, source: str, paper_id: str, s3_key: str):
    raw = s3.download(s3_key)

    if s3_key.endswith('.xml'):          # PMC XML path
        structured = parse_pmc_xml(raw)  # lxml direct parse
    else:                                # PDF path
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(raw)
            f.flush()
            tei_xml    = parse_pdf_to_tei(f.name)   # Grobid
            structured = parse_tei(tei_xml)          # lxml TEI parser
            structured['figures'] = [
                extract_and_describe_figure(
                    f.name, fig, doi_to_slug(structured['doi'])
                )
                for fig in structured['figures']
            ]

    doi_slug    = doi_to_slug(structured['doi'])
    parsed_key  = f'parsed/{doi_slug}/structured.json'
    s3.upload(json.dumps(structured).encode(), key=parsed_key)

    doi_registry.update(
        doi=structured['doi'],
        parse_status='parsed',
        s3_parsed_key=parsed_key,
        title=structured['title'],
        mesh_terms=structured.get('mesh_terms', []),
    )
    chunk_paper.delay(doi=structured['doi'], s3_key=parsed_key)  # -> Module 2
```

---

## Module 2 — Context-Aware Chunking

Converts `structured.json` into a list of `Chunk` objects ready for embedding. Primary strategy is document-structure-aware: each section becomes one chunk (or several overlapping sub-chunks if oversized). Figures and tables each get their own dedicated chunk. Every chunk receives a contextual header and a full metadata payload.

### 2.1 Chunking Parameters

| Parameter | Value | Rationale |
|---|---|---|
| `CHUNK_SIZE` | 512 tokens | Fits text-embedding-3-large context; tight embedding signal |
| `CHUNK_OVERLAP` | 80 tokens | ~15% overlap — prevents boundary sentence fragmentation |
| `MAX_SECTION_TOKENS` | 512 | Sections within budget = single chunk; above = recursive split |
| Tokeniser | tiktoken cl100k_base | Matches text-embedding-3-large vocabulary |

### 2.2 Chunk Types

| Type | Source element | Notes |
|---|---|---|
| `abstract` | `structured.json .abstract` | Always one chunk regardless of length |
| `section` | `structured.json .sections[]` | Recursive split if > 512 tokens |
| `figure` | `fig.caption + fig.description` | One chunk per figure; never split |
| `table` | `table.caption + table.markdown` | One chunk per table; never split |

### 2.3 Contextual Header Injection

Before embedding, prepend a structured header to every chunk. This ensures the embedding encodes both the document's identity and the section context — significantly improving retrieval precision for narrow queries where the chunk text alone lacks enough signal.

```python
# modules/module2_chunk/header.py

def inject_header(chunk: 'Chunk', paper: dict) -> str:
    lines = [
        f'Paper: {paper["title"]}',
        f'Journal: {paper["journal"]}  |  Date: {paper["pub_date"]}',
        f'Section: {chunk.section_heading}',
        '---',
        chunk.text,
    ]
    return '\n'.join(lines)

# Example output:
# Paper: Long-term renal effects of metformin in type 2 diabetes
# Journal: Diabetes Care  |  Date: 2023-08-01
# Section: Methods > Patient cohort
# ---
# A total of 4,218 patients with type 2 diabetes were recruited...
```

### 2.4 Recursive Splitting for Oversized Sections

```python
# modules/module2_chunk/chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

enc = tiktoken.get_encoding('cl100k_base')

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=80,
    length_function=count_tokens,
    separators=['\n\n', '\n', '. ', ' ', ''],
)

def chunk_section(section: dict, paper: dict) -> list:
    text = section['text']
    if count_tokens(text) <= 512:
        return [make_chunk(text, section, paper, sub_index=0)]
    sub_texts = splitter.split_text(text)
    return [make_chunk(t, section, paper, sub_index=i)
            for i, t in enumerate(sub_texts)]
```

### 2.5 Chunk Metadata Schema

Every `Chunk` carries this payload into Qdrant as the point's payload. All fields are indexed for filtering in Module 5.

```python
# shared/models.py
from pydantic import BaseModel

class Chunk(BaseModel):
    chunk_id:         str     # UUID4
    doi:              str
    doi_slug:         str     # URL-safe DOI for S3 paths
    title:            str
    authors:          list[str]
    journal:          str
    pub_date:         str     # YYYY-MM-DD
    pub_year:         int
    source_db:        str     # pubmed|europepmc|semanticscholar|biorxiv
    section_heading:  str
    chunk_index:      int     # global position within document
    sub_index:        int     # position within parent section (0 if not split)
    element_type:     str     # section|abstract|figure|table
    mesh_terms:       list[str]
    keywords:         list[str]
    text:             str     # raw chunk text (without header)
    text_with_header: str     # header-injected text used for embedding
    s3_parsed_key:    str     # back-pointer to structured.json
    has_figure:       bool
    has_table:        bool
    # Set by Module 3:
    dense_vector:     list[float] | None = None
    sparse_indices:   list[int]   | None = None
    sparse_values:    list[float] | None = None
```

---

## Module 3 — Tokenisation and Embedding Pipeline

Generates dense and sparse vectors for each chunk. Dense vectors via OpenRouter embeddings API (512-dimensional Matryoshka truncation). Sparse vectors via local FastEmbed SPLADE (no API call, no GPU required). Feeds completed `Chunk` objects to Module 4.

### 3.1 Dense Embedding — OpenRouter API

```python
# modules/module3_embed/dense.py
import httpx, asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

EMBEDDING_MODEL = 'openai/text-embedding-3-large'
EMBEDDING_DIMS  = 512      # Matryoshka truncation: 512 of 3072 dims
BATCH_SIZE      = 100      # chunks per API request
MAX_CONCURRENT  = 5        # simultaneous requests

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def _embed_batch(texts: list[str]) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            'https://openrouter.ai/api/v1/embeddings',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
            json={
                'model':      EMBEDDING_MODEL,
                'input':      texts,
                'dimensions': EMBEDDING_DIMS,   # Matryoshka truncation
            }
        )
        resp.raise_for_status()
        data = resp.json()['data']
        return [item['embedding']
                for item in sorted(data, key=lambda x: x['index'])]

async def embed_texts(texts: list[str]) -> list[list[float]]:
    sem     = asyncio.Semaphore(MAX_CONCURRENT)
    batches = [texts[i:i+BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]

    async def bounded(batch):
        async with sem:
            return await _embed_batch(batch)

    results = await asyncio.gather(*[bounded(b) for b in batches])
    return [emb for batch in results for emb in batch]
```

### 3.2 Sparse Embedding — FastEmbed SPLADE

SPLADE (Sparse Lexical and Expansion model) is a learned sparse encoder that expands query and document terms with related vocabulary using a transformer. It handles synonyms (renal/kidney, cardiac/heart, adverse/side effect) without a vocabulary lookup table, making it strictly better than raw BM25 for biomedical text.

```python
# modules/module3_embed/sparse.py
# pip install fastembed
from fastembed import SparseTextEmbedding

# Runs locally on CPU — no API call, no GPU required
# Downloads model on first run (~500MB); cached to ~/.cache/fastembed
sparse_model = SparseTextEmbedding(model_name='prithivida/Splade_PP_en_v1')

def generate_sparse_vectors(
    texts: list[str]
) -> list[dict[str, list]]:
    embeddings = list(sparse_model.embed(texts))
    return [
        {'indices': e.indices.tolist(), 'values': e.values.tolist()}
        for e in embeddings
    ]
```

### 3.3 Embedding Celery Task

```python
# modules/module3_embed/tasks.py

@celery_app.task(bind=True, max_retries=3)
def embed_chunks(self, doi: str):
    chunks = load_chunks_from_s3(doi)             # reads chunks/{doi_slug}.jsonl
    texts  = [c.text_with_header for c in chunks]

    # Dense (async, batched, API)
    dense_vecs  = asyncio.run(embed_texts(texts))

    # Sparse (sync, local)
    sparse_vecs = generate_sparse_vectors(texts)

    for chunk, dv, sv in zip(chunks, dense_vecs, sparse_vecs):
        chunk.dense_vector   = dv
        chunk.sparse_indices = sv['indices']
        chunk.sparse_values  = sv['values']

    save_chunks_to_s3(chunks, doi)
    doi_registry.update(doi, embed_status='embedded')
    ingest_to_qdrant.delay(doi=doi)               # -> Module 4
```

---

## Module 4 — Vector Store Ingestion

Creates and maintains the Qdrant collection. Ingests `Chunk` objects as Qdrant points with both dense (HNSW) and sparse (SPLADE) vectors plus the full metadata payload. Supports incremental upsert — re-running is always safe.

### 4.1 Qdrant Collection Setup

```python
# modules/module4_index/setup.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, SparseVectorParams, Distance,
    HnswConfigDiff, ScalarQuantizationConfig, ScalarType,
    PayloadSchemaType,
)

client     = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
COLLECTION = 'medical_papers'

def create_collection():
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            'dense': VectorParams(
                size=512,
                distance=Distance.COSINE,
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=200,
                    full_scan_threshold=10_000,
                ),
                quantization_config=ScalarQuantizationConfig(
                    type=ScalarType.INT8,   # SQ8: 4x memory reduction
                    quantile=0.99,
                    always_ram=True,
                ),
            )
        },
        sparse_vectors_config={
            'sparse': SparseVectorParams()  # SPLADE sparse vectors
        },
    )

    # Payload indexes — required for efficient metadata filtering in Module 5
    payload_indexes = [
        ('doi',          PayloadSchemaType.KEYWORD),
        ('pub_year',     PayloadSchemaType.INTEGER),
        ('pub_date',     PayloadSchemaType.KEYWORD),
        ('element_type', PayloadSchemaType.KEYWORD),
        ('mesh_terms',   PayloadSchemaType.KEYWORD),
        ('journal',      PayloadSchemaType.KEYWORD),
        ('source_db',    PayloadSchemaType.KEYWORD),
        ('has_figure',   PayloadSchemaType.BOOL),
        ('has_table',    PayloadSchemaType.BOOL),
    ]
    for field, schema_type in payload_indexes:
        client.create_payload_index(COLLECTION, field, schema_type)
```

### 4.2 Upsert

```python
# modules/module4_index/ingest.py
from qdrant_client.models import PointStruct, SparseVector

def ingest_chunks(chunks: list['Chunk']):
    points = [
        PointStruct(
            id=chunk.chunk_id,
            vector={
                'dense': chunk.dense_vector,
                'sparse': SparseVector(
                    indices=chunk.sparse_indices,
                    values=chunk.sparse_values,
                ),
            },
            payload={
                'doi':             chunk.doi,
                'title':           chunk.title,
                'authors':         chunk.authors,
                'journal':         chunk.journal,
                'pub_date':        chunk.pub_date,
                'pub_year':        chunk.pub_year,
                'source_db':       chunk.source_db,
                'section_heading': chunk.section_heading,
                'chunk_index':     chunk.chunk_index,
                'element_type':    chunk.element_type,
                'mesh_terms':      chunk.mesh_terms,
                'keywords':        chunk.keywords,
                'text':            chunk.text,
                's3_parsed_key':   chunk.s3_parsed_key,
                'has_figure':      chunk.has_figure,
                'has_table':       chunk.has_table,
            }
        )
        for chunk in chunks
    ]
    # Upsert is idempotent — same chunk_id safely overwrites
    client.upsert(collection_name=COLLECTION, points=points)
    doi_registry.update(chunks[0].doi, index_status='indexed')
```

### 4.3 Index Management

| Operation | Procedure |
|---|---|
| New paper | Upsert new points — no rebuild. DOI dedup in Module 1 prevents duplicates. |
| Paper retracted | `client.delete(COLLECTION, filter=FieldCondition(doi==target))`, then re-ingest corrected version. |
| Embedding model change | Create new collection `medical_papers_v2`, re-embed all papers, swap alias. Zero downtime. |
| Pre-operation snapshot | Call Qdrant snapshot API before any bulk operation. Stored in `qdrant_data` volume. |

---

## Module 5 — Retrieval Pipeline

Exposes four retrieval strategies behind a shared interface. All strategies accept an optional metadata filter and return the top-100 candidates as `RetrievalResult` objects for downstream reranking. The strategy pattern makes Modules 6 and 7 fully strategy-agnostic.

### 5.1 Shared Interface and Result Model

```python
# modules/module5_retrieve/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class RetrievalResult:
    chunk_id:  str
    score:     float
    payload:   dict
    rank:      int
    strategy:  str    # semantic | lexical | hybrid | tag

class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 100,
        filters: dict | None = None,
    ) -> list[RetrievalResult]: ...
```

### 5.2 Semantic Retrieval (Dense / HNSW)

```python
# modules/module5_retrieve/semantic.py
class SemanticRetriever(BaseRetriever):
    def retrieve(self, query, top_k=100, filters=None):
        query_vec = asyncio.run(embed_texts([query]))[0]
        hits = qdrant.search(
            collection_name=COLLECTION,
            query_vector=('dense', query_vec),
            query_filter=build_filter(filters),
            limit=top_k,
            with_payload=True,
        )
        return [RetrievalResult(h.id, h.score, h.payload, i, 'semantic')
                for i, h in enumerate(hits)]
```

### 5.3 Lexical Retrieval (Sparse / SPLADE)

```python
# modules/module5_retrieve/lexical.py
from qdrant_client.models import NamedSparseVector, SparseVector

class LexicalRetriever(BaseRetriever):
    def retrieve(self, query, top_k=100, filters=None):
        sv = generate_sparse_vectors([query])[0]
        hits = qdrant.search(
            collection_name=COLLECTION,
            query_vector=NamedSparseVector(
                name='sparse',
                vector=SparseVector(indices=sv['indices'], values=sv['values']),
            ),
            query_filter=build_filter(filters),
            limit=top_k,
            with_payload=True,
        )
        return [RetrievalResult(h.id, h.score, h.payload, i, 'lexical')
                for i, h in enumerate(hits)]
```

### 5.4 Hybrid Retrieval (Dense + Sparse, Qdrant-native RRF)

```python
# modules/module5_retrieve/hybrid.py
from qdrant_client.models import Prefetch, FusionQuery, Fusion

class HybridRetriever(BaseRetriever):
    def retrieve(self, query, top_k=100, filters=None):
        dv = asyncio.run(embed_texts([query]))[0]
        sv = generate_sparse_vectors([query])[0]
        f  = build_filter(filters)
        hits = qdrant.query_points(
            collection_name=COLLECTION,
            prefetch=[
                Prefetch(query=dv,
                         using='dense',  limit=top_k, filter=f),
                Prefetch(query=SparseVector(**sv),
                         using='sparse', limit=top_k, filter=f),
            ],
            query=FusionQuery(fusion=Fusion.RRF),  # Qdrant-native RRF
            limit=top_k,
            with_payload=True,
        )
        return [RetrievalResult(h.id, h.score, h.payload, i, 'hybrid')
                for i, h in enumerate(hits)]
```

### 5.5 Tag-Based Retrieval (Metadata Filter)

Tag retrieval is any other strategy run with a non-empty `filters` dict. `build_filter()` converts to a Qdrant `Filter` object.

```python
# modules/module5_retrieve/tag.py
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, Range

def build_filter(filters: dict | None) -> Filter | None:
    if not filters:
        return None
    conds = []
    if 'mesh_terms' in filters:
        conds.append(FieldCondition(
            key='mesh_terms', match=MatchAny(any=filters['mesh_terms'])))
    if 'year_from' in filters:
        conds.append(FieldCondition(
            key='pub_year',
            range=Range(gte=filters['year_from'],
                        lte=filters.get('year_to', 2100))))
    if 'journal' in filters:
        conds.append(FieldCondition(
            key='journal', match=MatchValue(value=filters['journal'])))
    if 'element_type' in filters:
        conds.append(FieldCondition(
            key='element_type', match=MatchValue(value=filters['element_type'])))
    if 'source_db' in filters:
        conds.append(FieldCondition(
            key='source_db', match=MatchValue(value=filters['source_db'])))
    return Filter(must=conds) if conds else None
```

---

## Module 6 — Reranking Pipeline

Two-stage pipeline. Stage 1: RRF fuses ranked lists from multiple retrievers into a single score-normalised ranking. Stage 2: MMR selects a diverse, relevant final set for the generator context window. Both are pure Python — no external service required.

### 6.1 Stage 1 — Reciprocal Rank Fusion (RRF)

RRF fuses ranked lists using only rank position — not raw scores. This avoids incompatible score scales between dense and sparse retrievers. The constant `k=60` smooths rank-1 dominance so that documents ranked 1st in one list and 3rd in another score higher than documents ranked 1st in only one list.

```python
# modules/module6_rerank/rrf.py

def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalResult]],
    k: int = 60,
) -> list[RetrievalResult]:
    """
    score(d) = sum_i  1 / (k + rank_i(d))
    rank is 1-indexed; missing documents score 0 for that list.
    """
    scores:   dict[str, float] = {}
    payloads: dict[str, dict]  = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list):   # rank is 0-indexed here
            cid = result.chunk_id
            scores[cid]   = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            payloads[cid] = result.payload

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        RetrievalResult(cid, scores[cid], payloads[cid], i, 'rrf')
        for i, cid in enumerate(sorted_ids)
    ]
```

### 6.2 Stage 2 — Max Marginal Relevance (MMR)

MMR iteratively selects the next chunk that maximises `lambda * relevance_to_query - (1-lambda) * max_similarity_to_already_selected`. `lambda=0.7` weights relevance over diversity — appropriate for specific medical queries. Use lower lambda (0.3–0.5) for broad exploratory queries.

```python
# modules/module6_rerank/mmr.py
import numpy as np

def cosine_sim(a: list[float], b: list[float]) -> float:
    a, b  = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0

def max_marginal_relevance(
    query_vector:      list[float],
    candidates:        list[RetrievalResult],
    candidate_vectors: dict[str, list[float]],  # chunk_id -> dense vector
    top_k:             int   = 8,
    lambda_param:      float = 0.7,
) -> list[RetrievalResult]:
    selected:  list[RetrievalResult] = []
    remaining: list[RetrievalResult] = list(candidates)

    while remaining and len(selected) < top_k:
        if not selected:
            # First pick: highest relevance to query
            best = max(
                remaining,
                key=lambda r: cosine_sim(candidate_vectors[r.chunk_id], query_vector)
            )
        else:
            sel_vecs = [candidate_vectors[s.chunk_id] for s in selected]
            def mmr_score(r):
                rel = cosine_sim(candidate_vectors[r.chunk_id], query_vector)
                red = max(cosine_sim(candidate_vectors[r.chunk_id], sv)
                          for sv in sel_vecs)
                return lambda_param * rel - (1 - lambda_param) * red
            best = max(remaining, key=mmr_score)
        selected.append(best)
        remaining.remove(best)

    return selected
```

### 6.3 Full Rerank Entry Point

```python
# modules/module6_rerank/pipeline.py

def rerank(
    query:         str,
    query_vector:  list[float],
    retrieval_map: dict[str, list[RetrievalResult]],
    rrf_top_n:     int   = 20,
    mmr_top_k:     int   = 8,
    lambda_param:  float = 0.7,
) -> list[RetrievalResult]:

    # Stage 1: RRF — fuse all retriever outputs
    fused = reciprocal_rank_fusion(list(retrieval_map.values()))
    top_n = fused[:rrf_top_n]

    # Fetch dense vectors for MMR similarity computation
    ids     = [r.chunk_id for r in top_n]
    vectors = fetch_vectors_from_qdrant(ids)  # batch qdrant.retrieve(with_vectors=True)

    # Stage 2: MMR — diverse final selection
    return max_marginal_relevance(
        query_vector, top_n, vectors,
        top_k=mmr_top_k, lambda_param=lambda_param
    )
```

---

## Module 7 — RAG Agent (CrewAI)

A three-agent CrewAI crew that answers medical research queries with full inline citations. Modules 5 and 6 are wrapped as CrewAI tools — the crew gets full retrieval power without coupling to its internals.

### 7.1 Agent Design

| Agent | Role | Tools |
|---|---|---|
| Retrieval Agent | Rewrites user query for optimal retrieval. Selects best strategy and filters. Detects multi-hop requirements and issues sub-queries. | `retrieve_tool`, `multi_hop_retrieve_tool` |
| Analysis Agent | Reads retrieved chunks. Assesses relevance and evidence quality. Identifies gaps and requests additional retrieval if needed. | `retrieve_tool` |
| Synthesis Agent | Produces the final answer. Cites every claim with `[DOI, Section]`. Flags claims not supported by retrieved evidence. | (none — generation only) |

### 7.2 Crew Setup

```python
# modules/module7_agent/crew.py
from crewai import Agent, Task, Crew, Process

LLM_CONFIG = {
    'model':    'openai/gpt-4o',
    'base_url': 'https://openrouter.ai/api/v1',
    'api_key':  OPENROUTER_API_KEY,
}

retrieval_agent = Agent(
    role='Medical Research Retrieval Specialist',
    goal='Find the most relevant, high-quality evidence from the research corpus.',
    backstory=(
        'Expert in medical literature search with deep knowledge of MeSH terms, '
        'study design, and biomedical terminology. Skilled at query rewriting '
        'and identifying when multi-hop reasoning is needed.'
    ),
    tools=[retrieve_tool, multi_hop_retrieve_tool],
    llm=LLM_CONFIG,
    verbose=True,
    max_iter=5,
)

analysis_agent = Agent(
    role='Medical Evidence Analyst',
    goal='Critically assess retrieved evidence for relevance, quality, completeness.',
    backstory=(
        'Expert in evidence-based medicine and critical appraisal. '
        'Evaluates study design, sample size, and statistical significance. '
        'Identifies when retrieved evidence is insufficient and requests more.'
    ),
    tools=[retrieve_tool],
    llm=LLM_CONFIG,
    verbose=True,
    max_iter=3,
)

synthesis_agent = Agent(
    role='Medical Research Synthesiser',
    goal='Produce accurate, fully-cited answers grounded in retrieved evidence.',
    backstory=(
        'Science communicator skilled at synthesising complex medical literature. '
        'Never makes claims beyond what the evidence supports. '
        'Always cites specific papers with DOI and section.'
    ),
    tools=[],
    llm=LLM_CONFIG,
    verbose=True,
)
```

### 7.3 CrewAI Tools

```python
# modules/module7_agent/tools.py
from crewai.tools import tool

@tool('retrieve_tool')
def retrieve_tool(
    query:        str,
    strategy:     str       = 'hybrid',
    mesh_terms:   list[str] = None,
    year_from:    int       = None,
    element_type: str       = None,
    top_k:        int       = 100,
) -> str:
    """
    Retrieve relevant chunks from the medical research corpus.
    strategy options: semantic | lexical | hybrid | tag
    Returns top chunks with DOI, section, and text formatted for agent reading.
    """
    filters   = build_filters(mesh_terms=mesh_terms, year_from=year_from,
                               element_type=element_type)
    retriever = get_retriever(strategy)
    results   = {strategy: retriever.retrieve(query, top_k, filters)}
    query_vec = asyncio.run(embed_texts([query]))[0]
    final     = rerank(query, query_vec, results)
    return format_chunks_for_agent(final)


@tool('multi_hop_retrieve_tool')
def multi_hop_retrieve_tool(
    initial_query: str,
    max_hops:      int = 3,
) -> str:
    """
    Multi-hop retrieval for questions requiring chained reasoning.
    Each hop generates a sub-query from the previous hop's context.
    Stops early if context is sufficient.
    """
    all_chunks    = []
    current_query = initial_query
    context       = ''

    for hop in range(max_hops):
        chunk_text = retrieve_tool(current_query, strategy='hybrid')
        all_chunks.append(chunk_text)
        context   += '\n' + chunk_text
        next_q     = _generate_followup_query(initial_query, context)
        if next_q is None:
            break
        current_query = next_q

    return '\n\n---\n\n'.join(all_chunks)
```

### 7.4 Tasks and Crew Kickoff

```python
# modules/module7_agent/crew.py  (continued)

def run_query(user_query: str) -> str:
    retrieval_task = Task(
        description=(
            f'User question: "{user_query}"\n'
            'Rewrite into an optimal retrieval query. '
            'Select the best strategy (semantic|lexical|hybrid|tag) '
            'and any relevant MeSH term or date filters. '
            'Use multi_hop_retrieve_tool if the question requires '
            'chained reasoning across multiple topics.'
        ),
        agent=retrieval_agent,
        expected_output='Retrieved chunks with DOI, section, and text.',
    )

    analysis_task = Task(
        description=(
            'Review all retrieved chunks. '
            'Assess each for relevance, study design, and evidence quality. '
            'If key information is missing, use retrieve_tool to fill gaps. '
            'Produce an annotated evidence summary.'
        ),
        agent=analysis_agent,
        expected_output='Evidence summary with quality annotations.',
        context=[retrieval_task],
    )

    synthesis_task = Task(
        description=(
            f'Answer the original question: "{user_query}"\n'
            'Use only the retrieved evidence. '
            'Cite every claim as [DOI, Section]. '
            'If evidence is insufficient, state this explicitly.'
        ),
        agent=synthesis_agent,
        expected_output='Final answer with inline citations.',
        context=[retrieval_task, analysis_task],
    )

    crew = Crew(
        agents=[retrieval_agent, analysis_agent, synthesis_agent],
        tasks=[retrieval_task, analysis_task, synthesis_task],
        process=Process.sequential,
        verbose=True,
    )
    return crew.kickoff()
```

---

## Module 8 — Evaluation Framework

Measures retrieval quality and end-to-end answer quality. RAGAS computes RAG-specific metrics using an LLM as judge. MLflow tracks experiments and ablation runs across retrieval strategies.

### 8.1 Test Set Format

```jsonl
// eval/eval_set.jsonl — one JSON object per line
// Minimum: 100 queries; target: 200 covering all query types
{"query": "What are the renal side effects of long-term metformin use?", "expected_answer": "Metformin is generally considered renal-safe at eGFR >= 30...", "source_dois": ["10.2337/dc23-0441", "10.1056/NEJMoa2200592"], "query_type": "factual", "mesh_terms": ["Metformin", "Kidney Diseases", "Diabetes Mellitus, Type 2"]}
```

`query_type` values: `factual` | `comparative` | `multi-hop` | `broad`

### 8.2 RAGAS Metrics

| Metric | What it measures | Target |
|---|---|---|
| Faithfulness | Are all claims in the answer supported by retrieved context? Catches hallucinations. | ≥ 0.85 |
| Answer relevance | Does the answer address the original question? A faithful but off-topic answer scores low. | ≥ 0.80 |
| Context precision | Of retrieved chunks, what fraction are actually relevant? High precision = low noise. | ≥ 0.70 |
| Context recall | Does retrieved context contain all info needed for the ground-truth answer? | ≥ 0.75 |

### 8.3 RAGAS Evaluation Code

```python
# modules/module8_eval/ragas_eval.py
from ragas import evaluate
from ragas.metrics import (faithfulness, answer_relevancy,
                            context_precision, context_recall)
from datasets import Dataset

def evaluate_strategy(test_set: list[dict], strategy: str) -> dict:
    rows = []
    for item in test_set:
        chunks = run_retrieval_and_rerank(item['query'], strategy=strategy)
        answer = run_query(item['query'])              # Module 7 full run
        rows.append({
            'question':     item['query'],
            'answer':       answer,
            'contexts':     [c.payload['text'] for c in chunks],
            'ground_truth': item['expected_answer'],
        })
    dataset = Dataset.from_list(rows)
    return evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy,
                 context_precision, context_recall],
    )
```

### 8.4 Retrieval Metrics

```python
# modules/module8_eval/retrieval_metrics.py

def recall_at_k(
    retrieved: list[RetrievalResult],
    relevant_dois: list[str],
    k: int
) -> float:
    top_k_dois = {r.payload['doi'] for r in retrieved[:k]}
    return len(top_k_dois & set(relevant_dois)) / max(len(relevant_dois), 1)

def mean_reciprocal_rank(
    retrieved: list[RetrievalResult],
    relevant_dois: list[str],
) -> float:
    for i, r in enumerate(retrieved):
        if r.payload['doi'] in relevant_dois:
            return 1.0 / (i + 1)
    return 0.0
```

### 8.5 MLflow Ablation Runner

```python
# modules/module8_eval/ablation.py
import mlflow

STRATEGIES = ['semantic', 'lexical', 'hybrid']

def run_ablation(test_set: list[dict]):
    mlflow.set_experiment('rag-medical-retrieval')
    for strategy in STRATEGIES:
        with mlflow.start_run(run_name=strategy):
            mlflow.log_params({
                'strategy':        strategy,
                'embedding_model': EMBEDDING_MODEL,
                'embedding_dims':  EMBEDDING_DIMS,
                'rrf_k':           60,
                'mmr_lambda':      0.7,
                'mmr_top_k':       8,
            })
            ragas = evaluate_strategy(test_set, strategy)
            for metric, score in ragas.items():
                mlflow.log_metric(metric, float(score))
            for k in [10, 100]:
                mlflow.log_metric(f'recall_at_{k}',
                                  mean_recall_at_k(test_set, strategy, k))
            mlflow.log_metric('mrr', mean_mrr(test_set, strategy))
```

---

## Module X — Observability (Cross-Cutting)

Structured logging, distributed tracing, and metrics collection wired across all modules. All components emit JSON-structured logs to Loki, OTel spans to the collector, and Prometheus metrics to the scrape endpoint.

### X.1 structlog — Structured Logging

```python
# shared/observability.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# Usage pattern across all modules:
log.info('chunk_retrieved',
    doi=chunk.doi, chunk_id=chunk.chunk_id,
    strategy='hybrid', score=0.87, latency_ms=12)

log.error('parse_failed',
    doi=doi, error=str(e), retry_count=self.request.retries)
```

### X.2 OpenTelemetry — Distributed Tracing

```python
from opentelemetry import trace
tracer = trace.get_tracer('rag-medical')

# Wrap critical path operations in spans:
with tracer.start_as_current_span('retrieve_and_rerank') as span:
    span.set_attribute('query', query)
    span.set_attribute('strategy', strategy)
    results = retriever.retrieve(query)
    span.set_attribute('candidates_returned', len(results))

# Key spans to instrument:
#  module1:   fetch_single_paper
#  module1b:  parse_paper, figure_describe (LLM call)
#  module2:   chunk_paper
#  module3:   embed_chunks (dense), generate_sparse
#  module4:   ingest_chunks
#  module5:   retrieve (per strategy)
#  module6:   rrf_fuse, mmr_select
#  module7:   crew_kickoff, tool_call (per tool invocation)
```

### X.3 Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

papers_fetched          = Counter('papers_fetched_total', '', ['source'])
papers_parsed           = Counter('papers_parsed_total', '', ['status'])
chunks_indexed          = Counter('chunks_indexed_total', '')
embedding_latency       = Histogram('embedding_latency_seconds', '')
retrieval_latency       = Histogram('retrieval_latency_seconds', '', ['strategy'])
rerank_latency          = Histogram('rerank_latency_seconds', '')
agent_run_latency       = Histogram('agent_run_latency_seconds', '')
openrouter_tokens       = Counter('openrouter_tokens_total', '', ['model', 'type'])
qdrant_collection_size  = Gauge('qdrant_points_total', '')
figure_describe_latency = Histogram('figure_describe_latency_seconds', '')
```

### X.4 Full Docker Compose

```yaml
# docker/docker-compose.yml
version: '3.9'
services:
  rabbitmq:
    image: rabbitmq:3-management
    ports: ['5672:5672', '15672:15672']

  redis:
    image: redis:7-alpine
    ports: ['6379:6379']

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: rag_registry
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: ['pg_data:/var/lib/postgresql/data']

  qdrant:
    image: qdrant/qdrant:v1.9.0
    ports: ['6333:6333']
    volumes: ['qdrant_data:/qdrant/storage']

  grobid:
    image: lfoppiano/grobid:0.8.0
    ports: ['8070:8070']
    deploy:
      resources:
        limits:
          memory: 4G

  celery_worker:
    build: .
    command: celery -A shared.celery_app worker --loglevel=info --concurrency=4
    env_file: .env
    depends_on: [rabbitmq, redis, postgres, grobid, qdrant]

  celery_beat:
    build: .
    command: celery -A shared.celery_app beat --loglevel=info
    env_file: .env
    depends_on: [rabbitmq, redis, postgres]

  prometheus:
    image: prom/prometheus
    volumes: ['./docker/prometheus.yml:/etc/prometheus/prometheus.yml']
    ports: ['9090:9090']

  grafana:
    image: grafana/grafana
    ports: ['3000:3000']
    volumes: ['grafana_data:/var/lib/grafana']

  loki:
    image: grafana/loki:2.9.0
    ports: ['3100:3100']

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - '/var/log:/var/log'
      - './docker/promtail-config.yml:/etc/promtail/config.yml'

volumes:
  pg_data:
  qdrant_data:
  grafana_data:
```

---

## Environment Variables Reference (.env.example)

| Variable | Module(s) | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | 1b, 3, 7 | All OpenRouter calls: embeddings, multimodal, LLM |
| `NCBI_API_KEY` | 1 | PMC fetch rate: 3 → 10 req/s |
| `SEMANTIC_SCHOLAR_API_KEY` | 1 | Semantic Scholar rate limit increase |
| `UNPAYWALL_EMAIL` | 1 | Required parameter by Unpaywall API |
| `AWS_BUCKET_NAME` | 1, 1b | S3 bucket for raw + parsed artefacts |
| `AWS_ACCESS_KEY_ID` | 1, 1b | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | 1, 1b | AWS credentials |
| `AWS_REGION` | 1, 1b | e.g. `us-east-1` |
| `DATABASE_URL` | All | `postgresql://rag:{pw}@postgres:5432/rag_registry` |
| `CELERY_BROKER_URL` | 1–4 | `amqp://guest:guest@rabbitmq:5672//` |
| `CELERY_RESULT_BACKEND` | 1–4 | `redis://redis:6379/0` |
| `QDRANT_URL` | 4, 5, 6 | e.g. `http://qdrant:6333` |
| `QDRANT_API_KEY` | 4, 5, 6 | Leave empty for local Docker; set for Qdrant Cloud |
| `GROBID_URL` | 1b | e.g. `http://grobid:8070` |
| `MLFLOW_TRACKING_URI` | 8 | e.g. `http://mlflow:5000` |
| `POSTGRES_PASSWORD` | docker-compose | PostgreSQL password |

---

## Python Dependencies (pyproject.toml)

```toml
[tool.poetry.dependencies]
python = "^3.11"

# HTTP + retry
httpx = "^0.27"
tenacity = "^8.2"

# Task queue
celery = {version = "^5.3", extras = ["redis"]}
celery-beat = "^2.6"
kombu = "^5.3"

# Database
sqlalchemy = "^2.0"
psycopg2-binary = "^2.9"
alembic = "^1.13"

# AWS
boto3 = "^1.34"

# PDF parsing
grobid-client-python = "^0.8"
lxml = "^5.1"
pymupdf = "^1.24"

# Chunking + tokenisation
langchain-text-splitters = "^0.2"
tiktoken = "^0.7"

# Embeddings + vector store
qdrant-client = "^1.9"
fastembed = "^0.3"
numpy = "^1.26"

# Agent
crewai = "^0.63"

# Evaluation
ragas = "^0.1"
mlflow = "^2.14"
datasets = "^2.20"

# Observability
structlog = "^24.1"
opentelemetry-sdk = "^1.24"
opentelemetry-exporter-otlp = "^1.24"
prometheus-client = "^0.20"

# Data models
pydantic = "^2.7"
pydantic-settings = "^2.2"
```

---

## Recommended Build Order for Claude Code

| Phase | Build target | Acceptance criterion |
|---|---|---|
| 1 | Infrastructure | `docker-compose up` healthy. Qdrant collection created. Postgres schema migrated. |
| 2 | Module 1 | All four source adapters fetch papers. S3 uploads verified. Postgres registry rows inserted. Celery Beat dispatches on schedule. |
| 3 | Module 1b | Grobid parses 5 test PDFs. `structured.json` matches schema. Figure PNGs uploaded to S3. LLM descriptions generated and stored. |
| 4 | Module 2 | Chunks produced for 3 papers. Metadata schema matches `Chunk` model. Header injection verified by inspection. No chunk exceeds 512 tokens. |
| 5 | Module 3 | Dense vectors shape `(512,)`. Sparse vectors non-empty. End-to-end embedding for 1 paper completes without error. |
| 6 | Module 4 | Qdrant collection point count matches chunk count. Payload indexes confirmed. Upsert re-run is idempotent. |
| 7 | Module 5 | All four retrievers return top-100 results for 3 test queries. Tag filter correctly restricts results. Interface contract enforced. |
| 8 | Module 6 | RRF fuses semantic + lexical lists correctly. MMR output is demonstrably more diverse than top-8 by score alone. |
| 9 | Module 7 | Full crew run on 5 queries. Citations present in all outputs. Multi-hop tool triggered on a chained question. |
| 10 | Module 8 | RAGAS scores computed for all strategies. MLflow experiment logged. Ablation table readable in MLflow UI. |
| 11 | Observability | JSON logs flowing to Loki. OTel spans visible in Grafana. Prometheus metrics scraped. Key dashboards built. |
