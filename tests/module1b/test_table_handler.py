def test_save_table_uploads_markdown():
    from unittest.mock import patch
    table = {'caption': 'Baseline characteristics', 'markdown': '| Age | 65 |\n| --- | --- |'}
    with patch('modules.module1b_parse.table_handler.s3') as mock_s3:
        from modules.module1b_parse.table_handler import save_table_to_s3
        save_table_to_s3(table, 'test_slug', 0)
    mock_s3.upload.assert_called_once()
    key = mock_s3.upload.call_args[1]['key']
    assert key == 'parsed/test_slug/tables/table_0.md'
    content = mock_s3.upload.call_args[0][0].decode()
    assert 'Baseline characteristics' in content
    assert '| Age | 65 |' in content
