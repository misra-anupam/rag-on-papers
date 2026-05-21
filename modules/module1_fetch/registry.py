from datetime import date

from sqlalchemy import text

from shared.db import get_session


def exists(doi: str) -> bool:
    with get_session() as session:
        row = session.execute(
            text('SELECT 1 FROM paper_registry WHERE doi = :doi'),
            {'doi': doi},
        ).fetchone()
        return row is not None


def upsert(
    doi: str,
    source: str,
    paper_id: str,
    s3_raw_key: str,
    fetch_status: str = 'fetched',
    title: str | None = None,
    authors: list | None = None,
    journal: str | None = None,
    publication_date: date | None = None,
    mesh_terms: list[str] | None = None,
) -> None:
    with get_session() as session:
        session.execute(
            text("""
                INSERT INTO paper_registry
                    (doi, paper_id, source, fetch_status, s3_raw_key,
                     title, authors, journal, publication_date, mesh_terms)
                VALUES
                    (:doi, :paper_id, :source, :fetch_status, :s3_raw_key,
                     :title, :authors::jsonb, :journal, :pub_date, :mesh_terms)
                ON CONFLICT (doi) DO UPDATE SET
                    fetch_status     = EXCLUDED.fetch_status,
                    s3_raw_key       = EXCLUDED.s3_raw_key,
                    updated_at       = NOW()
            """),
            {
                'doi': doi,
                'paper_id': paper_id,
                'source': source,
                'fetch_status': fetch_status,
                's3_raw_key': s3_raw_key,
                'title': title,
                'authors': __import__('json').dumps(authors) if authors else None,
                'journal': journal,
                'pub_date': publication_date,
                'mesh_terms': mesh_terms,
            },
        )


def update(
    doi: str,
    parse_status: str | None = None,
    embed_status: str | None = None,
    index_status: str | None = None,
    s3_parsed_key: str | None = None,
    title: str | None = None,
    mesh_terms: list[str] | None = None,
) -> None:
    fields: dict = {}
    if parse_status is not None:
        fields['parse_status'] = parse_status
    if embed_status is not None:
        fields['embed_status'] = embed_status
    if index_status is not None:
        fields['index_status'] = index_status
    if s3_parsed_key is not None:
        fields['s3_parsed_key'] = s3_parsed_key
    if title is not None:
        fields['title'] = title
    if mesh_terms is not None:
        fields['mesh_terms'] = mesh_terms
    if not fields:
        return

    set_clause = ', '.join(f'{k} = :{k}' for k in fields)
    fields['doi'] = doi
    with get_session() as session:
        session.execute(
            text(f'UPDATE paper_registry SET {set_clause} WHERE doi = :doi'),
            fields,
        )
