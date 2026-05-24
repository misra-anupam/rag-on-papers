import asyncio

from modules.module5_retrieve import get_retriever
from modules.module5_retrieve.base import RetrievalResult
from modules.module6_rerank.pipeline import rerank


def recall_at_k(
    retrieved: list[RetrievalResult],
    relevant_dois: list[str],
    k: int,
) -> float:
    top_k_dois = {r.payload["doi"] for r in retrieved[:k]}
    return len(top_k_dois & set(relevant_dois)) / max(len(relevant_dois), 1)


def mean_reciprocal_rank(
    retrieved: list[RetrievalResult],
    relevant_dois: list[str],
) -> float:
    for i, r in enumerate(retrieved):
        if r.payload.get("doi") in relevant_dois:
            return 1.0 / (i + 1)
    return 0.0


def run_retrieval_and_rerank(query: str, strategy: str = "hybrid") -> list[RetrievalResult]:
    from modules.module3_embed.dense import embed_texts

    retriever = get_retriever(strategy)
    results = {strategy: retriever.retrieve(query, top_k=100)}
    query_vec = asyncio.run(embed_texts([query]))[0]
    return rerank(query, query_vec, results)


def mean_recall_at_k(test_set: list[dict], strategy: str, k: int) -> float:
    scores = []
    for item in test_set:
        retrieved = run_retrieval_and_rerank(item["query"], strategy)
        scores.append(recall_at_k(retrieved, item.get("source_dois", []), k))
    return sum(scores) / len(scores) if scores else 0.0


def mean_mrr(test_set: list[dict], strategy: str) -> float:
    scores = []
    for item in test_set:
        retrieved = run_retrieval_and_rerank(item["query"], strategy)
        scores.append(mean_reciprocal_rank(retrieved, item.get("source_dois", [])))
    return sum(scores) / len(scores) if scores else 0.0
