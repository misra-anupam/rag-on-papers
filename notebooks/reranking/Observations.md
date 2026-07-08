# Observations

# Reranking strategies

* Cross-encoder : [CLS]Query[SEP]Doc[SEP] ->> [CLS]->Linear->Sigmoid
* ColBERT: Sum(max(Doc * Query))
* RRF + MMR

# RRF

For each retrieved doc on both lists, rerank = 1/(60 + rank(dense)) + 1/(60 + rank(sparse))
For each retrieved doc on either list, rerank = 1/(60 + rank(type))

    - For docs which have scored high/low in BOTH lists, maintain that ordering (higher are pushed higher, lower are pushed lower)
    - For docs which are present in either list, land up somewhere in the middle

# MMR

MMR = lambda * sim(doc, query) + (1-lambda) * max(sim(doc, higher_ranked_docs))

MMR helps in the following scenarios:
    - Multi-faceted questions
    - Summarization
    - Highly duplicate content in corpora

MMR hurts in the following scenarios:
    - Sharp context rich requirement for questions
    - Multiple information points are needed for voting/citation
