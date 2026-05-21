import pytest
from unittest.mock import MagicMock, patch


def _make_mock_session(fetchone_result=None):
    mock_result = MagicMock()
    mock_result.fetchone.return_value = fetchone_result
    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    return mock_session


def test_exists_returns_false_for_unknown_doi():
    with patch('modules.module1_fetch.registry.get_session') as mock_gs:
        mock_gs.return_value = _make_mock_session(fetchone_result=None)
        from modules.module1_fetch.registry import exists
        assert exists('10.9999/unknown') is False


def test_exists_returns_true_for_known_doi():
    with patch('modules.module1_fetch.registry.get_session') as mock_gs:
        mock_gs.return_value = _make_mock_session(fetchone_result=(1,))
        from modules.module1_fetch.registry import exists
        assert exists('10.1234/known') is True


def test_upsert_calls_execute():
    mock_session = _make_mock_session()
    with patch('modules.module1_fetch.registry.get_session') as mock_gs:
        mock_gs.return_value = mock_session
        from modules.module1_fetch.registry import upsert
        upsert(
            doi='10.1234/new',
            source='pubmed',
            paper_id='PMC12345',
            s3_raw_key='raw/pubmed/PMC12345.xml',
        )
    mock_session.execute.assert_called_once()


def test_update_skips_empty_fields():
    mock_session = _make_mock_session()
    with patch('modules.module1_fetch.registry.get_session') as mock_gs:
        mock_gs.return_value = mock_session
        from modules.module1_fetch.registry import update
        update(doi='10.1234/x')  # no fields to update
    mock_session.execute.assert_not_called()


def test_update_parse_status():
    mock_session = _make_mock_session()
    with patch('modules.module1_fetch.registry.get_session') as mock_gs:
        mock_gs.return_value = mock_session
        from modules.module1_fetch.registry import update
        update(doi='10.1234/x', parse_status='parsed')
    mock_session.execute.assert_called_once()
    call_args = str(mock_session.execute.call_args)
    assert 'parse_status' in call_args
