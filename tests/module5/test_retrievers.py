import pytest
from unittest.mock import MagicMock, patch
from modules.module5_retrieve.base import RetrievalResult


def _make_hit(chunk_id: str, score: float = 0.9) -> MagicMock:
    hit = MagicMock()
    hit.id      = chunk_id
    hit.score   = score
    hit.payload = {'doi': '10.1234/test', 'text': 'sample text', 'section_heading': 'Methods'}
    return hit


def test_semantic_retriever_returns_results():
    mock_client = MagicMock()
    mock_client.search.return_value = [_make_hit('abc'), _make_hit('def')]

    with patch('modules.module5_retrieve.semantic.get_client', return_value=mock_client), \
         patch('modules.module5_retrieve.semantic.asyncio') as mock_asyncio:

        mock_asyncio.run.return_value = [0.1] * 512
        from modules.module5_retrieve.semantic import SemanticRetriever
        retriever = SemanticRetriever(client=mock_client)
        results = retriever.retrieve('test query', top_k=10)

    assert len(results) == 2
    assert all(isinstance(r, RetrievalResult) for r in results)
    assert results[0].strategy == 'semantic'


def test_lexical_retriever_returns_results():
    mock_client = MagicMock()
    mock_client.search.return_value = [_make_hit('ghi')]

    with patch('modules.module5_retrieve.lexical.get_client', return_value=mock_client), \
         patch('modules.module5_retrieve.sparse.generate_sparse_vectors',
               return_value=[{'indices': [1, 2], 'values': [0.5, 0.3]}]):

        from modules.module5_retrieve.lexical import LexicalRetriever
        retriever = LexicalRetriever(client=mock_client)
        results = retriever.retrieve('renal metformin', top_k=10)

    assert len(results) == 1
    assert results[0].strategy == 'lexical'


def test_hybrid_retriever_returns_results():
    mock_client = MagicMock()
    mock_points = MagicMock()
    mock_points.points = [_make_hit('jkl'), _make_hit('mno')]
    mock_client.query_points.return_value = mock_points

    with patch('modules.module5_retrieve.hybrid.get_client', return_value=mock_client), \
         patch('modules.module5_retrieve.hybrid.asyncio') as mock_asyncio, \
         patch('modules.module3_embed.sparse.generate_sparse_vectors',
               return_value=[{'indices': [1], 'values': [0.9]}]):

        mock_asyncio.run.return_value = [[0.1] * 512]
        from modules.module5_retrieve.hybrid import HybridRetriever
        retriever = HybridRetriever(client=mock_client)
        results = retriever.retrieve('drug mechanism', top_k=10)

    assert len(results) == 2
    assert results[0].strategy == 'hybrid'


def test_get_retriever_factory():
    from modules.module5_retrieve import get_retriever
    from modules.module5_retrieve.semantic import SemanticRetriever
    from modules.module5_retrieve.lexical import LexicalRetriever
    from modules.module5_retrieve.hybrid import HybridRetriever

    with patch('modules.module5_retrieve.get_client'):
        assert isinstance(get_retriever('semantic'), SemanticRetriever)
        assert isinstance(get_retriever('lexical'), LexicalRetriever)
        assert isinstance(get_retriever('hybrid'), HybridRetriever)
        assert isinstance(get_retriever('tag'), HybridRetriever)
