import json
import tempfile

import structlog

from shared.celery_app import celery_app
from shared import s3
from shared.utils import doi_to_slug, synthetic_key
from shared.observability import papers_parsed

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def parse_paper(self, source: str, paper_id: str, s3_key: str):
    from modules.module1b_parse.grobid_client import parse_pdf_to_tei
    from modules.module1b_parse.tei_parser import parse_tei
    from modules.module1b_parse.pmc_parser import parse_pmc_xml
    from modules.module1b_parse.figure_handler import extract_and_describe_figure
    from modules.module1b_parse.table_handler import save_table_to_s3
    from modules.module1_fetch import registry

    raw = s3.download(s3_key)

    if s3_key.endswith('.xml'):
        structured = parse_pmc_xml(raw)
    else:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(raw)
            f.flush()
            pdf_path = f.name

        tei_xml    = parse_pdf_to_tei(pdf_path)
        structured = parse_tei(tei_xml)

        doi_slug = doi_to_slug(structured['doi']) if structured['doi'] else synthetic_key(
            structured.get('title', paper_id), []
        )
        structured['figures'] = [
            extract_and_describe_figure(pdf_path, fig, doi_slug)
            for fig in structured.get('figures', [])
            if fig.get('coords', {}).get('w', 0) > 0
        ]

    if not structured.get('doi'):
        structured['doi'] = synthetic_key(
            structured.get('title', paper_id),
            [a.get('name', '') for a in structured.get('authors', [])],
        )

    doi_slug   = doi_to_slug(structured['doi'])
    parsed_key = f'parsed/{doi_slug}/structured.json'
    s3.upload(json.dumps(structured, ensure_ascii=False).encode(), key=parsed_key)

    # Save metadata.json sidecar
    meta = {k: structured[k] for k in
            ('doi', 'title', 'authors', 'journal', 'pub_date', 'mesh_terms')
            if k in structured}
    s3.upload(json.dumps(meta).encode(), key=f'parsed/{doi_slug}/metadata.json')

    # Save tables to their own S3 paths
    for i, table in enumerate(structured.get('tables', [])):
        save_table_to_s3(table, doi_slug, i)

    registry.update(
        doi=structured['doi'],
        parse_status='parsed',
        s3_parsed_key=parsed_key,
        title=structured.get('title'),
        mesh_terms=structured.get('mesh_terms', []),
    )
    papers_parsed.labels(status='success').inc()
    log.info('paper_parsed', doi=structured['doi'], s3_key=parsed_key)

    from modules.module2_chunk.tasks import chunk_paper
    chunk_paper.delay(doi=structured['doi'], s3_key=parsed_key)
