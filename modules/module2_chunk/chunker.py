import json
import uuid

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from shared.models import Chunk
from shared.utils import doi_to_slug
from modules.module2_chunk.header import inject_header

enc = tiktoken.get_encoding('cl100k_base')

CHUNK_SIZE    = 512
CHUNK_OVERLAP = 80

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=lambda t: len(enc.encode(t)),
    separators=['\n\n', '\n', '. ', ' ', ''],
)


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def _base_fields(paper: dict) -> dict:
    authors = [a['name'] if isinstance(a, dict) else str(a)
               for a in paper.get('authors', [])]
    pub_date = paper.get('pub_date', '') or ''
    pub_year = int(pub_date[:4]) if len(pub_date) >= 4 and pub_date[:4].isdigit() else 0
    return {
        'doi':           paper.get('doi', ''),
        'doi_slug':      doi_to_slug(paper.get('doi', '')),
        'title':         paper.get('title', ''),
        'authors':       authors,
        'journal':       paper.get('journal', ''),
        'pub_date':      pub_date,
        'pub_year':      pub_year,
        'source_db':     paper.get('source_db', ''),
        'mesh_terms':    paper.get('mesh_terms', []),
        'keywords':      paper.get('keywords', []),
        's3_parsed_key': paper.get('s3_parsed_key', ''),
    }


def _make_chunk(text: str, section_heading: str, element_type: str,
                chunk_index: int, sub_index: int, paper: dict,
                has_figure: bool = False, has_table: bool = False) -> Chunk:
    base = _base_fields(paper)
    chunk = Chunk(
        chunk_id=str(uuid.uuid4()),
        **base,
        section_heading=section_heading,
        chunk_index=chunk_index,
        sub_index=sub_index,
        element_type=element_type,
        text=text,
        text_with_header='',  # filled below
        has_figure=has_figure,
        has_table=has_table,
    )
    chunk.text_with_header = inject_header(chunk, paper)
    return chunk


def chunk_abstract(paper: dict, chunk_index: int) -> list[Chunk]:
    text = paper.get('abstract', '').strip()
    if not text:
        return []
    return [_make_chunk(text, 'Abstract', 'abstract', chunk_index, 0, paper)]


def chunk_section(section: dict, paper: dict, chunk_index_start: int) -> list[Chunk]:
    text    = section.get('text', '').strip()
    heading = section.get('heading', '')
    if not text:
        return []
    if count_tokens(text) <= CHUNK_SIZE:
        return [_make_chunk(text, heading, 'section', chunk_index_start, 0, paper)]
    sub_texts = splitter.split_text(text)
    return [
        _make_chunk(t, heading, 'section', chunk_index_start + i, i, paper)
        for i, t in enumerate(sub_texts)
    ]


def chunk_figure(fig: dict, paper: dict, chunk_index: int) -> Chunk | None:
    caption     = fig.get('caption', '').strip()
    description = fig.get('description', '').strip()
    text = ' '.join(filter(None, [caption, description]))
    if not text:
        return None
    return _make_chunk(text, f'Figure {fig.get("fig_id", "")}',
                       'figure', chunk_index, 0, paper, has_figure=True)


def chunk_table(table: dict, paper: dict, chunk_index: int) -> Chunk | None:
    caption  = table.get('caption', '').strip()
    markdown = table.get('markdown', '').strip()
    text = '\n'.join(filter(None, [caption, markdown]))
    if not text:
        return None
    return _make_chunk(text, f'Table {table.get("table_id", "")}',
                       'table', chunk_index, 0, paper, has_table=True)


def chunk_paper(structured: dict, s3_parsed_key: str = '') -> list[Chunk]:
    paper = {**structured, 's3_parsed_key': s3_parsed_key}
    chunks: list[Chunk] = []
    idx = 0

    abstract_chunks = chunk_abstract(paper, idx)
    chunks.extend(abstract_chunks)
    idx += len(abstract_chunks)

    for section in structured.get('sections', []):
        sec_chunks = chunk_section(section, paper, idx)
        chunks.extend(sec_chunks)
        idx += len(sec_chunks)

    for fig in structured.get('figures', []):
        fig_chunk = chunk_figure(fig, paper, idx)
        if fig_chunk:
            chunks.append(fig_chunk)
            idx += 1

    for table in structured.get('tables', []):
        tbl_chunk = chunk_table(table, paper, idx)
        if tbl_chunk:
            chunks.append(tbl_chunk)
            idx += 1

    return chunks


def save_chunks_to_s3(chunks: list[Chunk], doi: str) -> str:
    from shared import s3
    from shared.utils import doi_to_slug
    slug = doi_to_slug(doi)
    key  = f'chunks/{slug}.jsonl'
    lines = '\n'.join(c.model_dump_json() for c in chunks)
    s3.upload(lines.encode(), key=key, content_type='application/jsonl')
    return key


def load_chunks_from_s3(doi: str) -> list[Chunk]:
    from shared import s3
    from shared.utils import doi_to_slug
    slug  = doi_to_slug(doi)
    key   = f'chunks/{slug}.jsonl'
    data  = s3.download(key)
    return [Chunk.model_validate_json(line) for line in data.decode().splitlines() if line]
