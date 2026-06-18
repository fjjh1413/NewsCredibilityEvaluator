# LLM Evidence Arbitration Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the LLM evaluates the complete evidence candidate pool, excludes unrelated evidence from scoring, supplies similar-news risk judgments, and preserves arbitration results across result-page reloads.

**Architecture:** Retrieval services only produce normalized candidates. The LLM returns validated evidence arbitration and similar-news decisions; the detection service derives effective evidence, dynamic score weights, and source-match flags. A compact JSON analysis payload is stored with the detection record so the detail API can restore the same result.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/Alembic, Python unittest/pytest, Vue 3, Vite.

---

### Task 1: Lock the missing behavior with regression tests

**Files:**
- Modify: `backend/tests/test_detect_api.py`
- Modify: `backend/tests/test_llm_service.py`
- Modify: `backend/tests/test_detection_history_api.py`

- [ ] Add a test proving all ten merged candidates reach `analyze_news_credibility`.
- [ ] Add tests proving empty effective evidence removes the evidence-quality weight.
- [ ] Add tests proving missing arbitration triggers one retry and never treats every candidate as effective.
- [ ] Add tests proving similar news is accepted only from LLM output with known candidate IDs and valid risk levels.
- [ ] Add a detail-response test proving persisted arbitration fields survive reload.
- [ ] Run the new tests and confirm they fail for the expected missing behavior.

### Task 2: Complete the LLM contract and arbitration flow

**Files:**
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/app/services/detection_service.py`

- [ ] Raise the LLM candidate limit from five to ten in both services.
- [ ] Make `evidence_arbitration` and `similar_news` mandatory output-contract fields.
- [ ] Retry once when arbitration is missing or invalid, and use the complete retry result when retry succeeds.
- [ ] Validate candidate IDs and similar-news risk levels against the candidate pool.
- [ ] Derive `knowledge_has_relevant_match` and `web_has_relevant_match` from effective evidence.
- [ ] Use `llm*0.5 + evidence*0.3 + rule*0.2` only when effective evidence exists; otherwise use `llm*0.6 + rule*0.4`.
- [ ] In LLM-degraded mode, do not score unarbitrated evidence; fall back to rule score only.
- [ ] Run targeted service tests until green.

### Task 3: Persist and restore arbitration results

**Files:**
- Modify: `backend/app/models/detection_record.py`
- Modify: `backend/app/schemas/detection.py`
- Modify: `backend/app/crud/detection_crud.py`
- Modify: `backend/app/api/v1/detect.py`
- Create: `backend/alembic/versions/<revision>_add_detection_analysis_payload.py`

- [ ] Add a nullable text `analysis_payload` column.
- [ ] Persist evidence quality, excluded evidence, similar news, arbitration status, and source-match flags as JSON.
- [ ] Merge the stored payload into `GET /api/detect/{id}` without exposing the raw storage field.
- [ ] Run CRUD, migration, and detail API tests until green.

### Task 4: Align the result page with the new contract

**Files:**
- Modify: `frontend/src/views/ResultView.vue`
- Modify: `frontend/src/components/RiskLevelTag.vue`

- [ ] Show explicit knowledge-base and web-match notices.
- [ ] Render only backend-validated LLM similar-news results.
- [ ] Keep auxiliary/unrated labels only as malformed-response fallbacks.
- [ ] Verify cached and reloaded results render the same sections.
- [ ] Run `npm run build` and confirm success.

### Task 5: Final verification

- [ ] Run the full backend test suite.
- [ ] Run the frontend production build.
- [ ] Re-run the Qinghai earthquake sample and confirm unrelated railway evidence is excluded, relevant web evidence is effective, and the score is not reduced by absent evidence.
- [ ] Review the final diff for unrelated changes and dead code.
