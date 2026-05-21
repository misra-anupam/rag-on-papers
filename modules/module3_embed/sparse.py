from functools import lru_cache

from fastembed import SparseTextEmbedding


@lru_cache(maxsize=1)
def _get_model() -> SparseTextEmbedding:
    # Downloaded once to ~/.cache/fastembed (~500 MB); CPU-only, no GPU required
    return SparseTextEmbedding(model_name='prithivida/Splade_PP_en_v1')


def generate_sparse_vectors(texts: list[str]) -> list[dict[str, list]]:
    model      = _get_model()
    embeddings = list(model.embed(texts))
    return [
        {'indices': e.indices.tolist(), 'values': e.values.tolist()}
        for e in embeddings
    ]
