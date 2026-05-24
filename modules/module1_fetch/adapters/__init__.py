from .biorxiv import BiorxivAdapter
from .europepmc import EuropePMCAdapter
from .pubmed import PubMedAdapter
from .semanticscholar import SemanticScholarAdapter

ADAPTERS = {
    "pubmed": PubMedAdapter(),
    "europepmc": EuropePMCAdapter(),
    "semanticscholar": SemanticScholarAdapter(),
    "biorxiv": BiorxivAdapter(),
}

__all__ = [
    "ADAPTERS",
    "BiorxivAdapter",
    "EuropePMCAdapter",
    "PubMedAdapter",
    "SemanticScholarAdapter",
]
