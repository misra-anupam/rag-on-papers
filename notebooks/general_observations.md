# Observations

## Performance improvements
* Improving query formulation
    - Multiple query generation
    - Previous chat context enrichment / query re-write
    - Query decomposition + Later combination of answers
    - Hybrid search
    - Parent-child retrieval
    - Metadata injection from prompt/context
    - Knowledge graph restructure
    - Feedback & enrichment loop

## Latency improvements
* Improving retrieval latency
    - Use scaler/binary quantized embedding HNSW search (Qdrant supports this)
    - Use metadata pre-filtering to search over a smaller corpus volume
    - Use vector DB cache before hitting the actual DB
    - For multiple query variants, use asyncio.gather() to fire retrieval searches parallely
    - Reduce embedding dimension

* Improving generation latency
    - Use speculative decoding*
    - Smaller model, smaller retrieved chunks
    - Use conn. pool for vector DB & LLM
    - LLM endpoint & app deployments in the same region
