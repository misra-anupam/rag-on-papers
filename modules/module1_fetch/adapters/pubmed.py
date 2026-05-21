import httpx
from lxml import etree

from shared.config import settings
from .base import BaseAdapter, RateLimiter, make_retry

ESEARCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
EFETCH  = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'


class PubMedAdapter(BaseAdapter):
    def __init__(self) -> None:
        rate = 10.0 if settings.ncbi_api_key else 3.0
        self._limiter = RateLimiter(rate)

    def _api_key_params(self) -> dict:
        return {'api_key': settings.ncbi_api_key} if settings.ncbi_api_key else {}

    @make_retry()
    async def search(self, query: str, max_results: int) -> list[str]:
        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                ESEARCH,
                params={
                    'db': 'pmc', 'term': query,
                    'retmax': max_results, 'retmode': 'json',
                    **self._api_key_params(),
                },
            )
            resp.raise_for_status()
            return resp.json()['esearchresult']['idlist']

    @make_retry()
    async def fetch(self, paper_id: str) -> bytes:
        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                EFETCH,
                params={
                    'db': 'pmc', 'id': paper_id,
                    'rettype': 'xml', 'retmode': 'xml',
                    **self._api_key_params(),
                },
            )
            resp.raise_for_status()
            return resp.content

    async def resolve_doi(self, paper_id: str) -> str | None:
        xml_bytes = await self.fetch(paper_id)
        return self.extract_doi(xml_bytes)

    @staticmethod
    def extract_doi(xml_bytes: bytes) -> str | None:
        try:
            root = etree.fromstring(xml_bytes)
            for elem in root.iter('article-id'):
                if elem.get('pub-id-type') == 'doi' and elem.text:
                    return elem.text.strip()
        except etree.XMLSyntaxError:
            pass
        return None
