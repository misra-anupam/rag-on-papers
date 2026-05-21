import asyncio

import structlog

from shared.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3)
def embed_chunks(self, doi: str):
    from modules.module2_chunk.chunker import load_chunks_from_s3, save_chunks_to_s3
    from modules.module3_embed.dense import embed_texts
    from modules.module3_embed.sparse import generate_sparse_vectors
    from modules.module1_fetch import registry

    chunks = load_chunks_from_s3(doi)
    if not chunks:
        log.warning('embed_chunks_empty', doi=doi)
        return

    texts = [c.text_with_header for c in chunks]

    dense_vecs  = asyncio.run(embed_texts(texts))
    sparse_vecs = generate_sparse_vectors(texts)

    for chunk, dv, sv in zip(chunks, dense_vecs, sparse_vecs):
        chunk.dense_vector   = dv
        chunk.sparse_indices = sv['indices']
        chunk.sparse_values  = sv['values']

    save_chunks_to_s3(chunks, doi)
    registry.update(doi, embed_status='embedded')
    log.info('chunks_embedded', doi=doi, count=len(chunks))

    from modules.module4_index.tasks import ingest_to_qdrant
    ingest_to_qdrant.delay(doi=doi)
