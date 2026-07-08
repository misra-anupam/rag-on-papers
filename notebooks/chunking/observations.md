# Observations

Factors by decreasing importance

1. Chunking strategies

    - Semantic
        Performs really well for context-dense longform documents with shifting topics. For larger documents, often there is lack
        of surrounding context when the extracted semantic chunks are actually smaller portions. Also, computationally expensive.

    - Structure-aware
        Works very well when all the corpora docs are of similar format, e.g. research papers. Enables search at similar granularity
        level across all docs.

    - Fixed size / recursive delimiter
        Generally the best approach when diverse types of docs are involved.

    - Parent-child from LlamaIndex


2. Chunk size

    Chunk size should match application use-case. Q&A -> smaller chunks; Summarization -> larger chunks

    - Small size (<256 tokens)
        Works best for fact based questions. Risk of losing surrounding context.

    - Medium size (~512 tokens)
        Works best for multi-hop questions. Best general purpose bet.

    - Large size (~1024 tokens)
        Peak relevancy and faithfulness. Context cliff around 2500 tokens for GPT 4 family of models.


3. Metadata enrichment
    Very important when filtering by tags & other conditions

<Preprocessing>
<Parent-child relationships>
<Late embedding>


4. Chunk overlap
    Not much measurable impact


Chunking coherence score - Embedding similarity within a chunk should be high, across chunk boundary it _may_ drop.
