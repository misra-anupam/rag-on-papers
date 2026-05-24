import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

from modules.module4_index.setup import COLLECTION, get_client
from shared.models import Chunk
from shared.observability import chunks_indexed, qdrant_collection_size

log = structlog.get_logger()


def ingest_chunks(chunks: list[Chunk], client: QdrantClient | None = None) -> None:
    client = client or get_client()

    points = [
        PointStruct(
            id=chunk.chunk_id,
            vector={
                "dense": chunk.dense_vector,
                "sparse": SparseVector(
                    indices=chunk.sparse_indices or [],
                    values=chunk.sparse_values or [],
                ),
            },
            payload={
                "doi": chunk.doi,
                "title": chunk.title,
                "authors": chunk.authors,
                "journal": chunk.journal,
                "pub_date": chunk.pub_date,
                "pub_year": chunk.pub_year,
                "source_db": chunk.source_db,
                "section_heading": chunk.section_heading,
                "chunk_index": chunk.chunk_index,
                "element_type": chunk.element_type,
                "mesh_terms": chunk.mesh_terms,
                "keywords": chunk.keywords,
                "text": chunk.text,
                "s3_parsed_key": chunk.s3_parsed_key,
                "has_figure": chunk.has_figure,
                "has_table": chunk.has_table,
            },
        )
        for chunk in chunks
        if chunk.dense_vector is not None
    ]

    if not points:
        log.warning("ingest_chunks_no_vectors", doi=chunks[0].doi if chunks else "unknown")
        return

    client.upsert(collection_name=COLLECTION, points=points)
    chunks_indexed.inc(len(points))

    collection_info = client.get_collection(COLLECTION)
    qdrant_collection_size.set(collection_info.points_count or 0)

    log.info("chunks_ingested", count=len(points), doi=chunks[0].doi if chunks else "unknown")


def delete_paper(doi: str, client: QdrantClient | None = None) -> None:
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = client or get_client()
    client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(must=[FieldCondition(key="doi", match=MatchValue(value=doi))]),
    )
    log.info("paper_deleted_from_qdrant", doi=doi)


def fetch_vectors_from_qdrant(
    ids: list[str], client: QdrantClient | None = None
) -> dict[str, list[float]]:
    client = client or get_client()
    records = client.retrieve(
        collection_name=COLLECTION,
        ids=ids,
        with_vectors=["dense"],
    )
    return {str(r.id): r.vector["dense"] for r in records if r.vector and "dense" in r.vector}
