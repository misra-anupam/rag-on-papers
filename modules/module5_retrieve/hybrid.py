import asyncio
import time

from qdrant_client import QdrantClient
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

from shared.observability import retrieval_latency
from modules.module4_index.setup import COLLECTION, get_client
from modules.module5_retrieve.base import BaseRetriever, RetrievalResult
from modules.module5_retrieve.tag import build_filter


class HybridRetriever(BaseRetriever):
    def __init__(self, client: QdrantClient | None = None) -> None:
        self._client = client or get_client()

    def retrieve(
        self, query: str, top_k: int = 100, filters: dict | None = None
    ) -> list[RetrievalResult]:
        from modules.module3_embed.dense import embed_texts
        from modules.module3_embed.sparse import generate_sparse_vectors

        dv = asyncio.run(embed_texts([query]))[0]
        sv = generate_sparse_vectors([query])[0]
        f  = build_filter(filters)

        t0 = time.perf_counter()
        hits = self._client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                Prefetch(query=dv,  using='dense',  limit=top_k, filter=f),
                Prefetch(
                    query=SparseVector(indices=sv['indices'], values=sv['values']),
                    using='sparse', limit=top_k, filter=f,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        retrieval_latency.labels(strategy='hybrid').observe(time.perf_counter() - t0)
        return [
            RetrievalResult(str(h.id), h.score, h.payload or {}, i, 'hybrid')
            for i, h in enumerate(hits.points)
        ]
