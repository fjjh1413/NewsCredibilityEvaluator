# RAG Engineering Optimization

## Status

Implemented on 2026-07-10.

## References

- Qdrant Hybrid Queries documents dense/sparse hybrid retrieval, RRF fusion,
  and multi-stage retrieval/reranking: https://qdrant.tech/documentation/search/hybrid-queries/
- Haystack hybrid retrieval combines embedding retrieval with BM25/keyword
  retrieval and then joins/reranks results:
  https://haystack.deepset.ai/tutorials/33_hybrid_retrieval
- LangChain ParentDocumentRetriever retrieves smaller child chunks first and
  returns parent documents for broader context:
  https://reference.langchain.com/python/langchain-classic/retrievers/parent_document_retriever/ParentDocumentRetriever
- Ragas context precision and recall define the evaluation shape for whether
  retrieved contexts are useful and complete:
  https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
  https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/context_recall/

## What Changed

The RAG path is now an engineered retrieval subsystem rather than a single
vector search call:

1. v2 retrieval still searches child chunks and aggregates parent documents.
2. Dense and lexical parent candidates are fused with normalized RRF by default.
3. `weighted_sum` remains available through `RAG_FUSION_STRATEGY` for rollback.
4. Detection builds a claim-aware query plan from backend extracted core claims.
5. Multiple query result sets are fused at parent-document level with RRF.
6. Query-aware supporting spans are attached to chunks and parent results.
7. A deterministic rerank layer reorders the final candidate pool using
   similarity, fusion signals, claim/query coverage, supporting spans, and
   source diversity.
8. An optional model rerank interface is available behind a feature flag.
9. RAG v2 index audit checks MySQL knowledge records against stored Chroma
   chunks and reports missing, extra, stale, unsynced, and wrong-version chunks.
10. Knowledge writes now use an outbox/job table for vector indexing. Callers
    enqueue `knowledge_index_jobs`; a background worker consumes the jobs and
    writes the active v1/v2/hybrid index through the shared sync executor.
11. RAG diagnostics are returned and persisted in `analysis_payload`.
12. Offline evaluation now reports RAG hit rate, MRR, parent recall, empty rate,
   and claim coverage.

## Runtime Controls

- `RAG_FUSION_STRATEGY=rrf|weighted_sum`
- `RAG_RRF_RANK_CONSTANT=60`
- `RAG_CLAIM_AWARE_ENABLED=true`
- `RAG_CLAIM_QUERY_COUNT=4`
- `RAG_SUPPORTING_SPANS_ENABLED=true`
- `RAG_SUPPORTING_SPAN_COUNT=2`
- `RAG_RULE_RERANK_ENABLED=true`
- `RAG_RERANK_POOL_SIZE=30`
- `RAG_MODEL_RERANK_ENABLED=false`
- `RAG_AUDIT_SAMPLE_LIMIT=200`
- `KNOWLEDGE_INDEX_JOB_ENABLED=true`
- `KNOWLEDGE_INDEX_JOB_INTERVAL_SECONDS=60`
- `KNOWLEDGE_INDEX_JOB_BATCH_SIZE=20`
- `KNOWLEDGE_INDEX_JOB_MAX_ATTEMPTS=3`
- `KNOWLEDGE_INDEX_JOB_RETRY_DELAY_SECONDS=60`

## Diagnostics

Each RAG evidence item can now include:

- `score_components.fusion_strategy`
- `score_components.dense_rank`
- `score_components.lexical_rank`
- `score_components.rrf_score`
- `score_components.multi_query_rrf_score`
- `query_match_count`
- `query_hits`
- `retrieval_queries`
- `retrieval_query_count`
- `retrieval_query_strategy`
- `supporting_spans`
- `rerank_original_rank`
- `rule_rerank_score`
- `model_rerank_score`
- `model_rerank_reason`
- `rerank_score`
- `rerank_stage`
- `diversity_adjusted_rerank_score`
- `rerank_order`

The detection result and detail payload include:

- `rag_query_count`
- `rag_query_strategy`
- `rag_supporting_span_count`

The RAG audit endpoint is:

```http
GET /api/rag/audit?sample_limit=200
```

It returns:

- `status`: `ok` or `failed`
- `issue_count`
- `issues_by_type`
- per-item issue lists with `missing_chunk`, `extra_chunk`, `stale_chunk`,
  `unsynced_item`, and `wrong_index_version`

## Design Notes

RRF is used for ranking, not for replacing the raw `similarity_score` produced
by retrieval. This keeps existing scoring thresholds stable while improving the
order and observability of candidates passed to LLM evidence arbitration.

Claim-aware retrieval is bounded and deterministic: the whole article query is
always first, then deduplicated core claims up to `RAG_CLAIM_QUERY_COUNT`.
Results are fused by parent document so repeated hits across claims strengthen
the candidate instead of creating duplicate evidence.

Supporting spans are intentionally lightweight. They do not remove context or
rewrite the document; they annotate chunks with matched excerpts so the system
can later support reranking, prompt compression, and UI explainability without
changing the stored index.

The rerank layer is deliberately split from fusion. RRF/MMR builds a candidate
pool; supporting spans add query-aware evidence; rule rerank produces the
served order. `RAG_MODEL_RERANK_ENABLED` only activates when a model rerank
provider is supplied, so the default path remains deterministic and offline.

The audit layer compares expected chunks generated from the current chunker and
settings with stored Chroma chunks. New writes include `content_hash`; older
vectors without that metadata are checked by hashing the stored document.

Knowledge indexing is eventually consistent by design. Admin-created,
admin-updated, manually vectorized, rebuilt, and crawler-imported knowledge
records are committed together with an outbox row in `knowledge_index_jobs`.
The worker later calls the same `sync_knowledge_vector` executor, which selects
v1 or v2/hybrid based on `RAG_INDEX_VERSION`. This removes the previous crawler
shortcut that wrote directly to the old single-vector Chroma path.

## Evaluation

Run:

```bash
python -m unittest evaluation.tests.test_ai_engineering_metrics evaluation.tests.test_ai_engineering_runner
python -m evaluation.ai_engineering.runner --cases evaluation/ai_engineering/sample_cases.jsonl --output .artifacts/ai_eval/summary.json
```

New metrics:

- `rag_hit_rate_at_k`
- `rag_mrr_at_k`
- `parent_recall_at_k`
- `rag_claim_coverage_at_k`
- `rag_empty_rate`
