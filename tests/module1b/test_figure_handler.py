import pytest
from unittest.mock import MagicMock, patch


def test_describe_figure_calls_openrouter():
    description = 'This figure shows a Kaplan-Meier curve with two groups.'
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'choices': [{'message': {'content': description}}]
    }

    with patch('modules.module1b_parse.figure_handler.httpx.post', return_value=mock_resp):
        from modules.module1b_parse.figure_handler import _describe_figure
        result = _describe_figure(b'fake-png-bytes', 'Kaplan-Meier survival curve')

    assert result == description


def test_extract_and_describe_figure_uploads_to_s3():
    """Verify S3 upload is called for both PNG and description."""
    fig = {
        'fig_id': 'fig1',
        'caption': 'Test figure',
        'coords': {'page': 1, 'x': 0.0, 'y': 0.0, 'w': 100.0, 'h': 100.0},
    }
    mock_page = MagicMock()
    mock_page.get_pixmap.return_value.tobytes.return_value = b'fake-png'
    mock_doc = MagicMock()
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)
    mock_doc.__len__ = MagicMock(return_value=2)

    with patch('modules.module1b_parse.figure_handler.fitz.open', return_value=mock_doc), \
         patch('modules.module1b_parse.figure_handler.s3') as mock_s3, \
         patch('modules.module1b_parse.figure_handler._describe_figure', return_value='A figure.'):

        from modules.module1b_parse.figure_handler import extract_and_describe_figure
        result = extract_and_describe_figure('fake.pdf', fig, 'test_slug')

    assert mock_s3.upload.call_count == 2  # PNG + description
    assert result['s3_img_key'].endswith('fig1.png')
    assert result['description'] == 'A figure.'
