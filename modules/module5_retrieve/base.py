from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievalResult:
    chunk_id: str
    score:    float
    payload:  dict
    rank:     int
    strategy: str  # semantic | lexical | hybrid | tag


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 100,
        filters: dict | None = None,
    ) -> list[RetrievalResult]: ...
