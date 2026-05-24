def test_inject_header_format(sample_paper, sample_chunk):
    from modules.module2_chunk.header import inject_header

    header_text = inject_header(sample_chunk, sample_paper)
    assert "Paper:" in header_text
    assert "Journal:" in header_text
    assert "Section:" in header_text
    assert "---" in header_text
    assert sample_paper["title"] in header_text
    assert sample_paper["journal"] in header_text


def test_header_is_prepended_to_chunk_text(sample_chunk):
    assert sample_chunk.text_with_header.startswith("Paper:")
    assert sample_chunk.text in sample_chunk.text_with_header
