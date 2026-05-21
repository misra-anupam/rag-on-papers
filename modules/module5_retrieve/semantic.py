import asyncio
import time

from qdrant_client import QdrantClient

from shared.observability import retrieval_latency
from modules.module4_index.setup import COLLECTION, get_client
from modules.module5_retrieve.base import BaseRetriever, RetrievalResult
from modules.module5_retrieve.tag import build_filter


class SemanticRetriever(BaseRetriever):
    def __init__(self, client: QdrantClient | None = None) -> None:
        self._client = client or get_client()

    def retrieve(
        self, query: str, top_k: int = 100, filters: dict | None = None
    ) -> list[RetrievalResult]:
        from modules.module3_embed.dense import embed_texts

        query_vec = asyncio.run(embed_texts([query]))[0]
        t0 = time.perf_counter()
        hits = self._client.search(
            collection_name=COLLECTION,
            query_vector=('dense', query_vec),
            query_filter=build_filter(filters),
            limit=top_k,
            with_payload=True,
        )
        retrieval_latency.labels(strategy='semantic').observe(time.perf_counter() - t0)
        return [
            RetrievalResult(str(h.id), h.score, h.payload or {}, i, 'semantic')
            for i, h in enumerate(hits)
        ]
