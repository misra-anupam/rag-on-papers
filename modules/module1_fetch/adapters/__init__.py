from .pubmed import PubMedAdapter
from .europepmc import EuropePMCAdapter
from .semanticscholar import SemanticScholarAdapter
from .biorxiv import BiorxivAdapter

ADAPTERS = {
    'pubmed':          PubMedAdapter(),
    'europepmc':       EuropePMCAdapter(),
    'semanticscholar': SemanticScholarAdapter(),
    'biorxiv':         BiorxivAdapter(),
}

__all__ = ['ADAPTERS', 'PubMedAdapter', 'EuropePMCAdapter',
           'SemanticScholarAdapter', 'BiorxivAdapter']
