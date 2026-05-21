import httpx

from .base import BaseAdapter, make_retry
from .unpaywall import UnpaywallAdapter

SEARCH_URL = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'


class EuropePMCAdapter(BaseAdapter):
    def __init__(self) -> None:
        self._unpaywall = UnpaywallAdapter()

    @make_retry()
    async def search(self, query: str, max_results: int) -> list[str]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                SEARCH_URL,
                params={
                    'query': query, 'format': 'json',
                    'pageSize': max_results, 'resultType': 'core',
                },
            )
            resp.raise_for_status()
            results = resp.json().get('resultList', {}).get('result', [])
            return [r['id'] for r in results if 'id' in r]

    @make_retry()
    async def fetch(self, paper_id: str) -> bytes:
        # paper_id is the Europe PMC accession; we need the full record for PDF URL
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                SEARCH_URL,
                params={
                    'query': f'EXT_ID:{paper_id}', 'format': 'json',
                    'pageSize': 1, 'resultType': 'core',
                },
            )
            resp.raise_for_status()
            results = resp.json().get('resultList', {}).get('result', [])
            if not results:
                raise ValueError(f'No record found for Europe PMC id {paper_id}')
            record = results[0]

        # Try to get an open-access PDF URL
        pdf_url = None
        for link in record.get('fullTextUrlList', {}).get('fullTextUrl', []):
            if link.get('availabilityCode') == 'OA' and link.get('documentStyle') == 'pdf':
                pdf_url = link.get('url')
                break

        if pdf_url:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                pdf_resp = await client.get(pdf_url)
                pdf_resp.raise_for_status()
                return pdf_resp.content

        # Fall back to JSON record bytes if no PDF available
        import json
        return json.dumps(record).encode()

    async def resolve_doi(self, paper_id: str) -> str | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                SEARCH_URL,
                params={
                    'query': f'EXT_ID:{paper_id}', 'format': 'json',
                    'pageSize': 1, 'resultType': 'core',
                },
            )
            if resp.status_code != 200:
                return None
            results = resp.json().get('resultList', {}).get('result', [])
            if results:
                return results[0].get('doi')
        return None
