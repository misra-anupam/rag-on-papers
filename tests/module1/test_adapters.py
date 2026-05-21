import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_pubmed_search_returns_ids():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'esearchresult': {'idlist': ['12345', '67890']}}
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        from modules.module1_fetch.adapters.pubmed import PubMedAdapter
        adapter = PubMedAdapter()
        ids = await adapter.search('diabetes', 10)

    assert isinstance(ids, list)
    assert '12345' in ids


@pytest.mark.asyncio
async def test_pubmed_fetch_returns_bytes():
    xml_content = b'<PubmedArticle><MedlineCitation></MedlineCitation></PubmedArticle>'
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = xml_content
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        from modules.module1_fetch.adapters.pubmed import PubMedAdapter
        adapter = PubMedAdapter()
        raw = await adapter.fetch('12345')

    assert isinstance(raw, bytes)
    assert len(raw) > 0


def test_pubmed_extract_doi():
    from modules.module1_fetch.adapters.pubmed import PubMedAdapter
    xml = b'''<article>
      <article-id pub-id-type="doi">10.1234/test.001</article-id>
    </article>'''
    doi = PubMedAdapter.extract_doi(xml)
    assert doi == '10.1234/test.001'


def test_pubmed_extract_doi_missing():
    from modules.module1_fetch.adapters.pubmed import PubMedAdapter
    doi = PubMedAdapter.extract_doi(b'<article></article>')
    assert doi is None


@pytest.mark.asyncio
async def test_unpaywall_returns_none_on_404():
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch('httpx.AsyncClient') as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        from modules.module1_fetch.adapters.unpaywall import UnpaywallAdapter
        adapter = UnpaywallAdapter()
        result = await adapter.resolve('10.9999/nonexistent')

    assert result is None
