"""Shared pytest fixtures."""

import pytest

from shared.models import Chunk


@pytest.fixture
def sample_paper() -> dict:
    return {
        "doi": "10.1234/test.001",
        "title": "Metformin and Renal Function in Type 2 Diabetes",
        "abstract": "Background: Metformin is widely used... Methods: ... Results: ...",
        "authors": [
            {"name": "Jane Smith", "affiliation": "Harvard"},
            {"name": "John Doe", "affiliation": "MIT"},
        ],
        "journal": "Diabetes Care",
        "pub_date": "2023-06-01",
        "mesh_terms": ["Metformin", "Kidney Diseases"],
        "keywords": ["metformin", "renal", "diabetes"],
        "sections": [
            {
                "heading": "Introduction",
                "text": "Metformin is the first-line treatment for type 2 diabetes. " * 10,
                "figure_refs": [],
                "table_refs": [],
            },
            {
                "heading": "Methods",
                "text": "We conducted a retrospective cohort study. " * 10,
                "figure_refs": ["fig1"],
                "table_refs": ["tbl1"],
            },
        ],
        "figures": [
            {
                "fig_id": "fig1",
                "caption": "Kaplan-Meier survival curve",
                "coords": {"page": 2, "x": 50.0, "y": 100.0, "w": 200.0, "h": 150.0},
                "s3_img_key": "",
                "description": "Survival curve showing...",
            }
        ],
        "tables": [
            {
                "table_id": "tbl1",
                "caption": "Baseline characteristics",
                "markdown": "| Variable | N |\n| --- | --- |\n| Age | 65 |",
            }
        ],
        "source_db": "pubmed",
        "s3_parsed_key": "parsed/10.1234_test.001/structured.json",
    }


@pytest.fixture
def sample_chunk(sample_paper) -> Chunk:
    from modules.module2_chunk.chunker import chunk_abstract

    chunks = chunk_abstract(sample_paper, 0)
    assert chunks, "sample_paper abstract is empty"
    return chunks[0]
