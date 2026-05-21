import httpx

from shared.config import settings
from .base import make_retry

BASE = 'https://api.unpaywall.org/v2'


class UnpaywallAdapter:
    @make_retry(max_attempts=3)
    async def resolve(self, doi: str) -> str | None:
        """Return a direct PDF URL for the DOI, or None if not available."""
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f'{BASE}/{doi}',
                params={'email': settings.unpaywall_email},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            for loc in data.get('oa_locations', []):
                url = loc.get('url_for_pdf')
                if url:
                    return url
        return None
