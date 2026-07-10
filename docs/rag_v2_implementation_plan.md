# RAG v2 Implementation Plan

## Goal

Upgrade the knowledge retrieval path from one vector per knowledge item to a
versioned, rollback-friendly evidence retrieval system:

- `v1`: existing one-vector-per-knowledge behavior.
- `v2`: chunk-level dense retrieval plus lexical retrieval and parent aggregation.
- `hybrid`: use v2 first and fall back to v1 when v2 returns no evidence.

The default remains `v1` so code deployment does not force an index migration.

## Rollout Gates

1. Build v2 chunks and vectors without deleting v1 vectors.
2. Compare v1 and v2 on fixed evaluation data using Recall@K, Hit@K, MRR, and
   stage latency.
3. Enable `RAG_INDEX_VERSION=hybrid` for internal testing.
4. Enable `RAG_INDEX_VERSION=v2` only after metrics prove recall gains without
   unacceptable latency regression.

## Rollback

Set `RAG_INDEX_VERSION=v1`. No Chroma cleanup is required for rollback because v2
chunks use `index_version=v2` metadata and chunk IDs under
`knowledge:{id}:chunk:{index}`.
