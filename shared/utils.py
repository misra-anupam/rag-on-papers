import hashlib
import re


def doi_to_slug(doi: str) -> str:
    """Convert a DOI to a filesystem/S3-safe slug."""
    return re.sub(r"[^\w.-]", "_", doi)


def synthetic_key(title: str, authors: list[str]) -> str:
    """SHA256-based surrogate key for papers without a DOI."""
    first_author = authors[0] if authors else ""
    digest = hashlib.sha256((title + first_author).encode()).hexdigest()[:16]
    return f"syn_{digest}"
