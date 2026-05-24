import time

from qdrant_client import QdrantClient
from qdrant_client.models import NamedSparseVector, SparseVector

from modules.module4_index.setup import COLLECTION, get_client
from modules.module5_retrieve.base import BaseRetriever, RetrievalResult
from modules.module5_retrieve.tag import build_filter
from shared.observability import retrieval_latency


class LexicalRetriever(BaseRetriever):
    def __init__(self, client: QdrantClient | None = None) -> None:
        self._client = client or get_client()

    def retrieve(
        self, query: str, top_k: int = 100, filters: dict | None = None
    ) -> list[RetrievalResult]:
        from modules.module3_embed.sparse import generate_sparse_vectors

        sv = generate_sparse_vectors([query])[0]
        t0 = time.perf_counter()
        hits = self._client.search(
            collection_name=COLLECTION,
            query_vector=NamedSparseVector(
                name="sparse",
                vector=SparseVector(indices=sv["indices"], values=sv["values"]),
            ),
            query_filter=build_filter(filters),
            limit=top_k,
            with_payload=True,
        )
        retrieval_latency.labels(strategy="lexical").observe(time.perf_counter() - t0)
        return [
            RetrievalResult(str(h.id), h.score, h.payload or {}, i, "lexical")
            for i, h in enumerate(hits)
        ]
