import pytest
from modules.module2_chunk.chunker import (
    chunk_abstract, chunk_section, chunk_paper, count_tokens, CHUNK_SIZE
)


def test_abstract_always_single_chunk(sample_paper):
    chunks = chunk_abstract(sample_paper, 0)
    assert len(chunks) == 1
    assert chunks[0].element_type == 'abstract'


def test_section_within_budget_is_single_chunk(sample_paper):
    section = {'heading': 'Short', 'text': 'This is a short section.', 'figure_refs': [], 'table_refs': []}
    chunks = chunk_section(section, sample_paper, 0)
    assert len(chunks) == 1


def test_oversized_section_is_split(sample_paper):
    # Create text that definitely exceeds 512 tokens
    long_text = ('Metformin reduces HbA1c levels significantly in patients with type 2 diabetes. ' * 40)
    assert count_tokens(long_text) > CHUNK_SIZE
    section = {'heading': 'Long', 'text': long_text, 'figure_refs': [], 'table_refs': []}
    chunks = chunk_section(section, sample_paper, 0)
    assert len(chunks) > 1
    for c in chunks:
        assert count_tokens(c.text_with_header) <= CHUNK_SIZE + 50  # small tolerance for header


def test_no_chunk_exceeds_token_limit(sample_paper):
    chunks = chunk_paper(sample_paper, s3_parsed_key='test.json')
    for c in chunks:
        tokens = count_tokens(c.text_with_header)
        assert tokens <= CHUNK_SIZE + 60, f'Chunk {c.chunk_id} has {tokens} tokens'


def test_chunk_indices_are_sequential(sample_paper):
    chunks = chunk_paper(sample_paper, s3_parsed_key='test.json')
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_figure_chunk_type(sample_paper):
    chunks = chunk_paper(sample_paper, s3_parsed_key='test.json')
    fig_chunks = [c for c in chunks if c.element_type == 'figure']
    assert len(fig_chunks) == len(sample_paper['figures'])
    for fc in fig_chunks:
        assert fc.has_figure is True


def test_table_chunk_type(sample_paper):
    chunks = chunk_paper(sample_paper, s3_parsed_key='test.json')
    tbl_chunks = [c for c in chunks if c.element_type == 'table']
    assert len(tbl_chunks) == len(sample_paper['tables'])
    for tc in tbl_chunks:
        assert tc.has_table is True
