# AI Engineering Quality Gate

This project already has an engineered detection flow: keyword extraction,
RAG retrieval, optional web search, LLM evidence arbitration, rule scoring,
persistence, and stage latency tracking. The missing production-grade piece is
a fast, repeatable quality gate that can run before merging changes and can
evaluate captured outputs without calling model providers.

## Objective

Implement AI engineering as a closed loop:

1. Define a stable case and prediction contract.
2. Capture or author representative cases.
3. Score task correctness, retrieval quality, evidence quality, degradation,
   and latency.
4. Fail CI when the system regresses.
5. Keep metrics pure and offline so the gate is deterministic.

## References

- OpenAI Evals treats an eval as a dataset plus evaluator logic, which maps well
  to `case -> prediction -> metrics`.
- Ragas context precision and context recall are the reference shape for ranked
  retrieval quality: relevant evidence should appear early, and enough relevant
  evidence should be retrieved.
- Promptfoo-style assertions inspired the explicit pass/fail gate: metrics are
  not just reports, they are merge criteria.

## Data Contract

Each JSONL case in `evaluation/ai_engineering/*.jsonl` has this shape:

```json
{
  "case_id": "AI-SMOKE-001",
  "input": {
    "title": "News title",
    "content": "News body"
  },
  "expected": {
    "risk_level": "high_risk",
    "score_range": [0, 45],
    "relevant_evidence_ids": ["kb:official-denial"]
  },
  "prediction": {
    "risk_level": "high_risk",
    "final_score": 28,
    "evidence_list": [{"evidence_id": "kb:official-denial"}],
    "candidate_evidence_list": [{"evidence_id": "kb:official-denial"}],
    "arbitration_status": "accepted",
    "quality_status": "ok",
    "stage_latency_ms": {"rag_search": 31, "llm_analysis": 220}
  }
}
```

External prediction files can also be supplied with `case_id` and `prediction`.
This lets CI run against checked-in smoke fixtures while larger offline runs can
evaluate fresh detector output.

Existing `evaluation.run_evaluation` output is supported through
`--results-csv`, which adapts `per_case_results.csv` into the same contract.

## Metrics

- `contract_valid_rate`: output contains required fields and sane ranges.
- `risk_level_accuracy`: predicted risk level matches the expected level.
- `score_in_range_rate`: final score lands inside the expected score band.
- `context_precision_at_k`: ranked evidence puts relevant IDs early.
- `context_recall_at_k`: ranked evidence retrieves the expected relevant IDs.
- `rag_hit_rate_at_k`: share of cases with at least one relevant retrieved item.
- `rag_mrr_at_k`: mean reciprocal rank of the first relevant retrieved item.
- `parent_recall_at_k`: parent-document recall for v2 chunk/parent retrieval.
- `rag_claim_coverage_at_k`: share of expected claim IDs covered by retrieved
  evidence metadata.
- `rag_empty_rate`: share of cases where retrieval returned no candidates.
- `degraded_rate`: provider errors, retries exhausted, parse failures, and
  explicit degraded statuses.
- `total_latency_ms_p95`: p95 latency from `total_latency_ms` or summed stages.
- `arbitration_quality_present_rate`: share of outputs exposing backend
  arbitration quality metadata.
- `claim_coverage_avg`: average claim coverage reported by arbitration quality
  controls.
- `high_quality_contradiction_rate`: share of cases with strong contradictory
  evidence signals.

## Commands

Run the unit tests:

```bash
python -m unittest evaluation.tests.test_ai_engineering_metrics evaluation.tests.test_ai_engineering_runner
```

Run the default smoke gate:

```bash
python -m evaluation.ai_engineering.runner \
  --cases evaluation/ai_engineering/sample_cases.jsonl \
  --output .artifacts/ai_eval/summary.json
```

Run against external predictions:

```bash
python -m evaluation.ai_engineering.runner \
  --cases evaluation/ai_engineering/sample_cases.jsonl \
  --predictions .artifacts/detect_predictions.jsonl \
  --output .artifacts/ai_eval/summary.json
```

Run against an existing offline evaluation CSV:

```bash
python -m evaluation.ai_engineering.runner \
  --results-csv evaluation/output/per_case_results.csv \
  --output .artifacts/ai_eval/summary.json
```

## Boundaries

This gate does not call the live detector. That is intentional: CI should have
one deterministic offline gate. A separate scheduled or release workflow can
use the existing `evaluation.run_evaluation` service-level runner to capture
fresh predictions, then feed them into this gate.
