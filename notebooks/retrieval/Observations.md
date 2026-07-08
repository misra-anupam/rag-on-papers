# Observations

# Retrieval
Dense + Hybrid

## Quality improvement:

* Use prefiltering on metadata
* Improving dense retrieval quality -> Change the embedding model
* Improving sparse retrieval quality -> Multi-query generation for better keyword matches
* Try colBERT style retrieval


## Latency improvement:
* Scaler quantization
4x memory reduction from 8 bytes(float32) -> 1 byte(int8)
    - More doc vectors fit in memory/cache, HNSW search hits to disk reduce
    - Computation speeds up due to drastically reduced vector size
    - Re-computation of final set at float32 for better final result
      (rescore=True needs to be enabled and an oversampling factor needs to be specified
      for e.g. for top 20, 40 would be sampled in 1st pass on int8 and 20 sampled from it
      in the 2nd pass using float32)
* If using Matryoshka based embeddings, do a two-stage retrieval, first with smaller embedding size and then
  with a larger embedding size
