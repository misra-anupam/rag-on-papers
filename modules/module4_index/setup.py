import structlog
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    PayloadSchemaType,
    ScalarQuantizationConfig,
    ScalarType,
    SparseVectorParams,
    VectorParams,
)

from shared.config import settings

log = structlog.get_logger()

COLLECTION = "medical_papers"


def get_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        # api_key=settings.qdrant_api_key or None,
    )


def create_collection(client: QdrantClient | None = None) -> None:
    client = client or get_client()

    try:
        client.get_collection(COLLECTION)
        log.info("qdrant_collection_exists", collection=COLLECTION)
        return
    except (UnexpectedResponse, Exception):
        pass  # collection doesn't exist yet

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": VectorParams(
                size=512,
                distance=Distance.COSINE,
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=200,
                    full_scan_threshold=10_000,
                ),
                quantization_config=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                ),
            )
        },
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )
    log.info("qdrant_collection_created", collection=COLLECTION)

    payload_indexes = [
        ("doi", PayloadSchemaType.KEYWORD),
        ("pub_year", PayloadSchemaType.INTEGER),
        ("pub_date", PayloadSchemaType.KEYWORD),
        ("element_type", PayloadSchemaType.KEYWORD),
        ("mesh_terms", PayloadSchemaType.KEYWORD),
        ("journal", PayloadSchemaType.KEYWORD),
        ("source_db", PayloadSchemaType.KEYWORD),
        ("has_figure", PayloadSchemaType.BOOL),
        ("has_table", PayloadSchemaType.BOOL),
    ]
    for field, schema_type in payload_indexes:
        client.create_payload_index(COLLECTION, field, schema_type)
        log.info("qdrant_payload_index_created", field=field)


def delete_collection(client: QdrantClient | None = None) -> None:
    client = client or get_client()
    client.delete_collection(COLLECTION)
    log.info("qdrant_collection_deleted", collection=COLLECTION)


if __name__ == "__main__":
    create_collection()
