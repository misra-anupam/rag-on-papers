# Comparison among vector DBs

## Pinecone
Good but its only a commercial offering. We want OSS and self-managed for the criticality and sensitivity of our healthcare data.

## Qdrant
Great option. Use when there are 1M - 100M vectors.
* Built using Rust
* Easy to self-host
* Very low latency
* Good support of dense & sparse embeddings; good filtering options

1536-dim vector -> 6kB memory; 1M -> 6 GB

* Binary quantization enables it to be very fast

## Weaviate
Good option for smaller scale. Heavy Java runtime

## Milvus
The actual GOAT for production RAG systems.
More difficult to host. Use for 1B+ vectors.
Very high throughput.
