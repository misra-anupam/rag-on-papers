from datetime import datetime, timedelta

import httpx

from .base import BaseAdapter, make_retry

BASE = "https://api.biorxiv.org/details"
PDF_BASE = "https://www.biorxiv.org/content"


class BiorxivAdapter(BaseAdapter):
    """Fetches preprints from bioRxiv and medRxiv (last 7 days)."""

    @make_retry()
    async def search(self, query: str = "", max_results: int = 500) -> list[str]:
        end = datetime.utcnow().date()
        start = end - timedelta(days=7)
        ids: list[str] = []
        for server in ("biorxiv", "medrxiv"):
            url = f"{BASE}/{server}/{start}/{end}/json"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                collection = resp.json().get("collection", [])
                for paper in collection[:max_results]:
                    doi = paper.get("doi")
                    if doi:
                        ids.append(doi)
        return ids

    @make_retry()
    async def fetch(self, paper_id: str) -> bytes:
        # paper_id is the DOI for biorxiv
        pdf_url = f"{PDF_BASE}/{paper_id}.full.pdf"
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()
            return resp.content

    async def resolve_doi(self, paper_id: str) -> str | None:
        # For biorxiv the paper_id IS the DOI
        return paper_id
