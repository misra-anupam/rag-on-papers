from modules.module2_chunk.chunker import chunk_abstract, chunk_figure, chunk_table


def test_abstract_ignores_length(sample_paper):
    # Even a very long abstract should be a single chunk
    sample_paper = dict(sample_paper)
    sample_paper["abstract"] = "Long abstract. " * 200
    chunks = chunk_abstract(sample_paper, 0)
    assert len(chunks) == 1


def test_figure_chunk_never_split(sample_paper):
    fig = sample_paper["figures"][0]
    chunk = chunk_figure(fig, sample_paper, 0)
    assert chunk is not None
    assert chunk.element_type == "figure"
    assert chunk.has_figure is True


def test_table_chunk_never_split(sample_paper):
    table = sample_paper["tables"][0]
    chunk = chunk_table(table, sample_paper, 0)
    assert chunk is not None
    assert chunk.element_type == "table"
    assert chunk.has_table is True


def test_figure_chunk_contains_caption_and_description(sample_paper):
    fig = dict(sample_paper["figures"][0])
    fig["description"] = "Shows a survival curve with p<0.05."
    chunk = chunk_figure(fig, sample_paper, 0)
    assert chunk is not None
    assert fig["caption"] in chunk.text
    assert fig["description"] in chunk.text


def test_empty_figure_returns_none(sample_paper):
    fig = {"fig_id": "fig_empty", "caption": "", "coords": {}, "s3_img_key": "", "description": ""}
    chunk = chunk_figure(fig, sample_paper, 0)
    assert chunk is None
