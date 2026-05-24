from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_embed_batch_returns_sorted_vectors():
    fake_vectors = [[0.1] * 512, [0.2] * 512]
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {"index": 1, "embedding": fake_vectors[1]},
            {"index": 0, "embedding": fake_vectors[0]},
        ],
        "usage": {"total_tokens": 20},
    }

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        from modules.module3_embed.dense import _embed_batch

        result = await _embed_batch(["text one", "text two"])

    assert result[0] == fake_vectors[0]
    assert result[1] == fake_vectors[1]


@pytest.mark.asyncio
async def test_embed_texts_batches_correctly():
    """101 texts should produce 2 batches (100 + 1)."""
    call_count = 0

    async def fake_embed(texts):
        nonlocal call_count
        call_count += 1
        return [[0.0] * 512] * len(texts)

    with patch("modules.module3_embed.dense._embed_batch", side_effect=fake_embed):
        from modules.module3_embed.dense import embed_texts

        result = await embed_texts(["text"] * 101)

    assert call_count == 2
    assert len(result) == 101
    assert len(result[0]) == 512
