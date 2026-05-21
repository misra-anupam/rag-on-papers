import pytest
from unittest.mock import MagicMock, patch
import uuid
from shared.models import Chunk


def make_chunk(doi: str = '10.1234/test') -> Chunk:
    return Chunk(
        chunk_id=str(uuid.uuid4()),
        doi=doi, doi_slug='10_1234_test',
        title='Test Paper', authors=['Jane Smith'], journal='NEJM',
        pub_date='2023-01-01', pub_year=2023, source_db='pubmed',
        section_heading='Abstract', chunk_index=0, sub_index=0,
        element_type='abstract', mesh_terms=['Diabetes'], keywords=[],
        text='Metformin reduces HbA1c.', text_with_header='Paper: Test\n---\nMetformin reduces HbA1c.',
        s3_parsed_key='parsed/test/structured.json',
        has_figure=False, has_table=False,
        dense_vector=[0.1] * 512,
        sparse_indices=[1, 5, 10],
        sparse_values=[0.5, 0.3, 0.8],
    )


def test_ingest_chunks_calls_upsert():
    chunks = [make_chunk(), make_chunk()]
    mock_client = MagicMock()
    mock_client.get_collection.return_value.points_count = 2

    with patch('modules.module4_index.ingest.get_client', return_value=mock_client):
        from modules.module4_index.ingest import ingest_chunks
        ingest_chunks(chunks, client=mock_client)

    mock_client.upsert.assert_called_once()
    call_args = mock_client.upsert.call_args
    assert call_args[1]['collection_name'] == 'medical_papers'
    assert len(call_args[1]['points']) == 2


def test_ingest_skips_chunks_without_vectors():
    chunk = make_chunk()
    chunk.dense_vector = None
    mock_client = MagicMock()

    with patch('modules.module4_index.ingest.get_client', return_value=mock_client):
        from modules.module4_index.ingest import ingest_chunks
        ingest_chunks([chunk], client=mock_client)

    mock_client.upsert.assert_not_called()


def test_ingest_is_idempotent():
    """Calling upsert twice with same chunk_id should not raise."""
    chunk = make_chunk()
    mock_client = MagicMock()
    mock_client.get_collection.return_value.points_count = 1

    with patch('modules.module4_index.ingest.get_client', return_value=mock_client):
        from modules.module4_index.ingest import ingest_chunks
        ingest_chunks([chunk], client=mock_client)
        ingest_chunks([chunk], client=mock_client)

    assert mock_client.upsert.call_count == 2


def test_delete_paper():
    mock_client = MagicMock()
    with patch('modules.module4_index.ingest.get_client', return_value=mock_client):
        from modules.module4_index.ingest import delete_paper
        delete_paper('10.1234/test', client=mock_client)
    mock_client.delete.assert_called_once()
