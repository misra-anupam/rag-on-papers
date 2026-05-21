import os
import tempfile
from pathlib import Path

import httpx
import structlog

from shared.config import settings

log = structlog.get_logger()

CONFIG_PATH = Path(__file__).parent / 'grobid_config.json'

# Grobid process endpoint
PROCESS_URL = '{server}/api/processFulltextDocument'


def parse_pdf_to_tei(pdf_path: str) -> str:
    """Send a PDF to Grobid and return the TEI XML string."""
    url = PROCESS_URL.format(server=settings.grobid_url)
    with open(pdf_path, 'rb') as f:
        files = {'input': (os.path.basename(pdf_path), f, 'application/pdf')}
        params = {
            'generateIDs': '1',
            'consolidateHeader': '1',
            'consolidateCitations': '0',
            'includeRawCitations': '0',
            'includeRawAffiliations': '0',
            'teiCoordinates': 'figure',
            'segmentSentences': '1',
        }
        resp = httpx.post(url, files=files, data=params, timeout=120.0)

    if resp.status_code == 503:
        raise RuntimeError('Grobid unavailable (503) — will retry')
    resp.raise_for_status()
    log.info('grobid_parsed', pdf=pdf_path, bytes=len(resp.content))
    return resp.text


def grobid_is_alive() -> bool:
    try:
        resp = httpx.get(f'{settings.grobid_url}/api/isalive', timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
