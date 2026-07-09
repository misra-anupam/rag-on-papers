# Observations

## Retrieval metrics

**Recall@k:**
Compares unordered relevance of retrieved chunks.
Recall@k = (all relevant docs) intersection (docs retrieved @ k)  / (all relevant docs)

**Precision@k**
Precision@k = (all relevant docs) intersection (docs retrieved @ k)  / k

On increasing k, recall always increases, as it increases the changes of more relevant docs to be extracted.
However, the precision would drop. To keep the precision high, you would need to have some custom pipeline.

### Improving Recall

* Multi-query search
* Metadata pre-filtering

### Improving Precision(Reaching high precision after high recall)

Retrieved 50 docs at the retrieval stage, got a high recall. But cannot send all of them into the model context.
Good re-ranking strategies will be needed to drive up the precision.

RRF happens before re-ranking. Re-ranking re-ranks based on doc/query similarity/interaction.

* Cross encoder
* colBERT
* Custom model based reranking
* Domain fine-tuned LLM rerankers

MMR happens after reranking

**MRR(Mean Reciprocal Rank):**
When **only one** chunk is meant to contain the information, you do a 1/rank(target_chunk).
Hopefully it appears at earlier ranks and MRR value is high.

**NDCG(Normalized Discounted Cumulative Gain):**

External ratings of chunk relevance are used to rate the overall retrieval methodology.

1. Use RRF to rank the docs across dense & sparse embeddings -> [doc1, doc2, doc3, doc4, doc5]
2. Use a LLM judge to score relevance of documents againt the query between [0,3] -> For 5 docs, it gives relevance like [3,2,1,0,1]
3. Calculate DCG@k = summation( relevance(d,q)/ log_2(rank) ) -> DCG@5 = 3/(log_2(1+1)) + 2/(log_2(1+2)) + 1/(log_2(1+3)) + 0/(log_2(1+4)) + 1/(log_2(1+5))
4. Calculate IDCG@k = Ideal position of relevant docs FROM ALL DOCS, i.e. [3,3,2,1,1] -> summation( relevance(d,q)/ log_2(rank) )
5. Calculate NDCG@k = DCG@k/IDCG@k

IDCG@k=DCG of the best-possible top-k, drawn from ALL relevant docs in the corpus (or your labeled pool) for that query
It's the ranking you'd get if an oracle retriever perfectly sorted every relevant document that exists (by relevance grade) and you took the top k of that.


## Generation metrics

* Faithfulness/groundedness
Faithfulness = Claims supported by context / Claims present in answer
RAGAS uses this claim decomposition technique; better to use a LLM-as-a-judge here instead of NLI techniques.

* Factual correctness
Requires ground truth.

* Relevance to question
Generates synthetic questions against the obtained answer, and find the average sim. b/w these questions and the user's question.


# RAGAS

Retrieval Augmented Generation ASessment
When a metric output is wrong, often the intermediate LLM judge prompt/model is the issue.
It measures across 8 metrics. For three metrics, ground truth is not reqd..

* Faithfulness
* Precision
* Relevance

Ground truth required for
* Recall
* Entity recall
* Answer correctness
* Answer similarity
* Aspect critique(Separate agent specific metric)
