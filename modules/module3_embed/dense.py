import asyncio
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shared.config import settings
from shared.observability import embedding_latency, openrouter_tokens

EMBEDDING_MODEL = "openai/text-embedding-3-large"
EMBEDDING_DIMS = 512
BATCH_SIZE = 100
MAX_CONCURRENT = 5


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def _embed_batch(texts: list[str]) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": EMBEDDING_MODEL,
                "input": texts,
                "dimensions": EMBEDDING_DIMS,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        if usage.get("total_tokens"):
            openrouter_tokens.labels(model=EMBEDDING_MODEL, type="total").inc(usage["total_tokens"])
        items = data["data"]
        return [item["embedding"] for item in sorted(items, key=lambda x: x["index"])]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    batches = [texts[i : i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]

    async def bounded(batch):
        async with sem:
            return await _embed_batch(batch)

    t0 = time.perf_counter()
    results = await asyncio.gather(*[bounded(b) for b in batches])
    embedding_latency.observe(time.perf_counter() - t0)
    return [emb for batch in results for emb in batch]
