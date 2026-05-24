import json

import structlog

from shared import s3
from shared.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def chunk_paper(self, doi: str, s3_key: str):
    from modules.module2_chunk.chunker import chunk_paper as _chunk
    from modules.module2_chunk.chunker import save_chunks_to_s3

    raw = s3.download(s3_key)
    structured = json.loads(raw.decode())

    chunks = _chunk(structured, s3_parsed_key=s3_key)
    chunks_key = save_chunks_to_s3(chunks, doi)

    log.info("paper_chunked", doi=doi, chunk_count=len(chunks), s3_key=chunks_key)

    from modules.module3_embed.tasks import embed_chunks

    embed_chunks.delay(doi=doi)
