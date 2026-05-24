import uuid

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doi: str
    doi_slug: str  # URL-safe DOI for S3 paths
    title: str
    authors: list[str]
    journal: str
    pub_date: str  # YYYY-MM-DD
    pub_year: int
    source_db: str  # pubmed|europepmc|semanticscholar|biorxiv
    section_heading: str
    chunk_index: int  # global position within document
    sub_index: int  # position within parent section (0 if not split)
    element_type: str  # section|abstract|figure|table
    mesh_terms: list[str]
    keywords: list[str]
    text: str  # raw chunk text (without header)
    text_with_header: str  # header-injected text used for embedding
    s3_parsed_key: str  # back-pointer to structured.json
    has_figure: bool
    has_table: bool
    # Set by Module 3:
    dense_vector: list[float] | None = None
    sparse_indices: list[int] | None = None
    sparse_values: list[float] | None = None
