import asyncio

import httpx
from crewai.tools import tool

from shared.config import settings
from modules.module5_retrieve import get_retriever
from modules.module5_retrieve.tag import build_filter
from modules.module6_rerank.pipeline import rerank


def _embed_query(query: str) -> list[float]:
    from modules.module3_embed.dense import embed_texts
    return asyncio.run(embed_texts([query]))[0]


def format_chunks_for_agent(results) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        p = r.payload
        lines.append(
            f'[{i}] DOI: {p.get("doi", "N/A")} | '
            f'Section: {p.get("section_heading", "")} | '
            f'Score: {r.score:.4f}\n'
            f'{p.get("text", "")}\n'
        )
    return '\n---\n'.join(lines)


def _build_filters(
    mesh_terms: list[str] | None = None,
    year_from: int | None = None,
    element_type: str | None = None,
    source_db: str | None = None,
) -> dict:
    f: dict = {}
    if mesh_terms:
        f['mesh_terms'] = mesh_terms
    if year_from:
        f['year_from'] = year_from
    if element_type:
        f['element_type'] = element_type
    if source_db:
        f['source_db'] = source_db
    return f


@tool('retrieve_tool')
def retrieve_tool(
    query: str,
    strategy: str = 'hybrid',
    mesh_terms: list[str] | None = None,
    year_from: int | None = None,
    element_type: str | None = None,
    top_k: int = 100,
) -> str:
    """
    Retrieve relevant chunks from the medical research corpus.
    strategy: semantic | lexical | hybrid | tag
    Returns top chunks with DOI, section, and text.
    """
    filters   = _build_filters(mesh_terms=mesh_terms, year_from=year_from,
                                element_type=element_type)
    retriever = get_retriever(strategy)
    results   = {strategy: retriever.retrieve(query, top_k, filters or None)}
    query_vec = _embed_query(query)
    final     = rerank(query, query_vec, results)
    return format_chunks_for_agent(final)


@tool('multi_hop_retrieve_tool')
def multi_hop_retrieve_tool(
    initial_query: str,
    max_hops: int = 3,
) -> str:
    """
    Multi-hop retrieval for questions requiring chained reasoning.
    Each hop generates a sub-query from the previous hop's context.
    """
    all_chunks:    list[str] = []
    current_query: str       = initial_query
    context:       str       = ''

    for _ in range(max_hops):
        chunk_text    = retrieve_tool(current_query, strategy='hybrid')
        all_chunks.append(chunk_text)
        context      += '\n' + chunk_text
        next_q        = _generate_followup_query(initial_query, context)
        if next_q is None:
            break
        current_query = next_q

    return '\n\n---\n\n'.join(all_chunks)


def _generate_followup_query(original_query: str, context: str) -> str | None:
    """Ask the LLM whether more retrieval is needed; return a follow-up query or None."""
    prompt = (
        f'Original question: {original_query}\n\n'
        f'Retrieved context so far:\n{context[:3000]}\n\n'
        'Is the context sufficient to answer the question fully? '
        'If yes, respond with exactly: SUFFICIENT\n'
        'If not, respond with a single follow-up search query (one sentence only).'
    )
    resp = httpx.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={'Authorization': f'Bearer {settings.openrouter_api_key}'},
        json={
            'model': 'openai/gpt-4o',
            'max_tokens': 100,
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    text = resp.json()['choices'][0]['message']['content'].strip()
    return None if text.upper().startswith('SUFFICIENT') else text
