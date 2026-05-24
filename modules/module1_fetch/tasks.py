import asyncio

import httpx
import structlog

from shared import s3
from shared.celery_app import celery_app
from shared.observability import papers_fetched

log = structlog.get_logger()


def _get_adapters():
    from modules.module1_fetch.adapters import ADAPTERS

    return ADAPTERS


def _get_registry():
    from modules.module1_fetch import registry

    return registry


@celery_app.task(bind=True, max_retries=3)
def fetch_pubmed_batch(self, query: str, max_results: int = 500):
    from modules.module1_fetch.adapters import PubMedAdapter

    adapter = PubMedAdapter()
    pmcids = asyncio.run(adapter.search(query, max_results))
    log.info("pubmed_batch_dispatching", count=len(pmcids))
    for pmcid in pmcids:
        fetch_single_paper.delay(source="pubmed", paper_id=pmcid)


@celery_app.task(bind=True, max_retries=3)
def fetch_europepmc_batch(self, query: str, max_results: int = 300):
    from modules.module1_fetch.adapters import EuropePMCAdapter

    adapter = EuropePMCAdapter()
    ids = asyncio.run(adapter.search(query, max_results))
    log.info("europepmc_batch_dispatching", count=len(ids))
    for paper_id in ids:
        fetch_single_paper.delay(source="europepmc", paper_id=paper_id)


@celery_app.task(bind=True, max_retries=3)
def fetch_semantic_scholar_batch(self, query: str, max_results: int = 200):
    from modules.module1_fetch.adapters import SemanticScholarAdapter

    adapter = SemanticScholarAdapter()
    ids = asyncio.run(adapter.search(query, max_results))
    log.info("semanticscholar_batch_dispatching", count=len(ids))
    for paper_id in ids:
        fetch_single_paper.delay(source="semanticscholar", paper_id=paper_id)


@celery_app.task(bind=True, max_retries=3)
def fetch_biorxiv_batch(self):
    from modules.module1_fetch.adapters import BiorxivAdapter

    adapter = BiorxivAdapter()
    ids = asyncio.run(adapter.search())
    log.info("biorxiv_batch_dispatching", count=len(ids))
    for paper_id in ids:
        fetch_single_paper.delay(source="biorxiv", paper_id=paper_id)


@celery_app.task(
    bind=True,
    max_retries=5,
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def fetch_single_paper(self, source: str, paper_id: str):
    from modules.module1_fetch import registry
    from modules.module1_fetch.adapters import ADAPTERS

    adapter = ADAPTERS[source]

    doi = asyncio.run(adapter.resolve_doi(paper_id))
    if doi and registry.exists(doi):
        log.info("paper_already_exists", doi=doi, source=source)
        return

    raw_bytes = asyncio.run(adapter.fetch(paper_id))
    ext = "xml" if source == "pubmed" else "pdf"
    s3_key = f"raw/{source}/{paper_id}.{ext}"
    s3.upload(raw_bytes, key=s3_key)

    # Use synthetic key if no DOI
    from shared.utils import synthetic_key

    effective_doi = doi or synthetic_key(paper_id, [])

    registry.upsert(
        doi=effective_doi,
        source=source,
        paper_id=paper_id,
        s3_raw_key=s3_key,
        fetch_status="fetched",
    )
    papers_fetched.labels(source=source).inc()
    log.info("paper_fetched", doi=effective_doi, source=source, s3_key=s3_key)

    from modules.module1b_parse.tasks import parse_paper

    parse_paper.delay(source=source, paper_id=paper_id, s3_key=s3_key)
