from unittest.mock import MagicMock, patch

import numpy as np


def _make_mock_embedding(indices, values):
    emb = MagicMock()
    emb.indices = np.array(indices)
    emb.values = np.array(values)
    return emb


def test_generate_sparse_vectors_returns_nonempty():
    mock_model = MagicMock()
    mock_model.embed.return_value = [
        _make_mock_embedding([10, 42, 300], [0.5, 0.8, 0.3]),
        _make_mock_embedding([5, 100], [0.9, 0.1]),
    ]

    with patch("modules.module3_embed.sparse._get_model", return_value=mock_model):
        from modules.module3_embed.sparse import generate_sparse_vectors

        result = generate_sparse_vectors(["text one", "text two"])

    assert len(result) == 2
    assert result[0]["indices"] == [10, 42, 300]
    assert result[0]["values"] == [0.5, 0.8, 0.3]
    assert len(result[1]["indices"]) > 0


def test_sparse_output_format():
    mock_model = MagicMock()
    mock_model.embed.return_value = [_make_mock_embedding([1], [1.0])]

    with patch("modules.module3_embed.sparse._get_model", return_value=mock_model):
        from modules.module3_embed.sparse import generate_sparse_vectors

        result = generate_sparse_vectors(["any text"])

    assert "indices" in result[0]
    assert "values" in result[0]
    assert isinstance(result[0]["indices"], list)
    assert isinstance(result[0]["values"], list)
