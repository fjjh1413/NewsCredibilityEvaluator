# Evidence Arbitration Optimization

## Goal

Upgrade evidence arbitration from "LLM returns a valid ranked list" to an
auditable evidence-quality subsystem. The optimized path keeps the existing
failure policy, but adds deterministic backend checks around the LLM decision.

## Runtime Flow

1. Assign stable `candidate_id` values to every candidate.
2. Extract deterministic core claims from the news title/content.
3. Pass neutralized evidence order and core claims into the LLM prompt.
4. Ask the LLM to rank/reject evidence and attach `claim_ids` to ranked items.
5. Validate candidate IDs, uniqueness, scores, stance, reason, and optional
   `claim_ids`.
6. Calibrate accepted evidence with backend signals:
   - source reliability
   - freshness
   - extraction completeness
   - near-duplicate penalty
   - claim coverage
   - contradiction strength
7. Persist and return `core_claims`, calibrated evidence fields, and
   `arbitration_quality`.

## Why This Shape

- OpenAI Evals frames quality work as dataset plus evaluator logic; this project
  now records fields that can be evaluated offline.
- Ragas context precision/recall emphasize ranked retrieval quality; the backend
  now keeps calibrated rank metadata instead of trusting retrieval order.
- Promptfoo-style assertions informed the explicit contract and CI gate:
  arbitration quality should be testable, not just described in prose.

## Compatibility

The contract version is now `2.1`. Missing `claim_ids` do not fail validation
yet, so older providers or tests can still pass. New prompts request `claim_ids`,
and backend quality metrics expose whether claim coverage is actually present.

The final score formula is intentionally unchanged in this slice. The system
returns calibrated evidence scores and arbitration quality summary; using those
directly in `final_score` should be a separate calibrated rollout with threshold
sensitivity tests.
