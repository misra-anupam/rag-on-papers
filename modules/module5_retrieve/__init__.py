from modules.module5_retrieve.base import BaseRetriever, RetrievalResult
from modules.module5_retrieve.hybrid import HybridRetriever
from modules.module5_retrieve.lexical import LexicalRetriever
from modules.module5_retrieve.semantic import SemanticRetriever


def get_retriever(strategy: str) -> BaseRetriever:
    match strategy:
        case "semantic":
            return SemanticRetriever()
        case "lexical":
            return LexicalRetriever()
        case "hybrid" | "tag":
            return HybridRetriever()
        case _:
            raise ValueError(f"Unknown retrieval strategy: {strategy}")


__all__ = [
    "BaseRetriever",
    "HybridRetriever",
    "LexicalRetriever",
    "RetrievalResult",
    "SemanticRetriever",
    "get_retriever",
]
