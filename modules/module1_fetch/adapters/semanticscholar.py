import httpx

from shared.config import settings

from .base import BaseAdapter, RateLimiter, make_retry
from .unpaywall import UnpaywallAdapter

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "paperId,title,authors,year,doi,isOpenAccess,openAccessPdf,abstract"


class SemanticScholarAdapter(BaseAdapter):
    def __init__(self) -> None:
        # 100 req/5min unauthed ≈ 0.33/s; higher with key
        rate = 1.0 if settings.semantic_scholar_api_key else 0.33
        self._limiter = RateLimiter(rate)
        self._unpaywall = UnpaywallAdapter()

    def _headers(self) -> dict:
        if settings.semantic_scholar_api_key:
            return {"x-api-key": settings.semantic_scholar_api_key}
        return {}

    @make_retry()
    async def search(self, query: str, max_results: int) -> list[str]:
        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                SEARCH_URL,
                params={"query": query, "fields": FIELDS, "limit": min(max_results, 100)},
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return [p["paperId"] for p in data if "paperId" in p]

    @make_retry()
    async def fetch(self, paper_id: str) -> bytes:
        await self._limiter.acquire()
        # Fetch paper details to get PDF URL
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}",
                params={"fields": FIELDS},
                headers=self._headers(),
            )
            resp.raise_for_status()
            paper = resp.json()

        pdf_url = (paper.get("openAccessPdf") or {}).get("url")

        # Fall back to Unpaywall if no direct PDF URL
        if not pdf_url and paper.get("doi"):
            pdf_url = await self._unpaywall.resolve(paper["doi"])

        if not pdf_url:
            raise ValueError(f"No open-access PDF found for paper {paper_id}")

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            pdf_resp = await client.get(pdf_url)
            pdf_resp.raise_for_status()
            return pdf_resp.content

    async def resolve_doi(self, paper_id: str) -> str | None:
        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}",
                params={"fields": "doi"},
                headers=self._headers(),
            )
            if resp.status_code != 200:
                return None
            doi = resp.json().get("doi")
            return str(doi) if doi else None
