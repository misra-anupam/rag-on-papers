import structlog

from shared.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def ingest_to_qdrant(self, doi: str):
    from modules.module1_fetch import registry
    from modules.module2_chunk.chunker import load_chunks_from_s3
    from modules.module4_index.ingest import ingest_chunks

    chunks = load_chunks_from_s3(doi)
    if not chunks:
        log.warning("ingest_empty", doi=doi)
        return

    ingest_chunks(chunks)
    registry.update(doi, index_status="indexed")
    log.info("paper_indexed", doi=doi, chunks=len(chunks))
