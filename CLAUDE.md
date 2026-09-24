# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智闻辨真 (ZhiYun BianZhen) — a news credibility evaluation system based on RAG + LLM. Users input a news title and body; the system retrieves similar evidence from a knowledge base via Chroma vector search, calls DeepSeek for LLM analysis, applies rule-based scoring, and returns a structured credibility assessment with risk level, evidence matches, and suggestions.

- **Backend**: FastAPI (Python 3.14) at `http://127.0.0.1:8000`, Swagger at `/docs`
- **Frontend**: Vue 3 + Vite + Element Plus + ECharts at `http://127.0.0.1:5173`
- **Database**: MySQL (`zhiyun_bianzhen`) + Chroma (local persistent vector store)
- **LLM**: DeepSeek API (`deepseek-chat` by default)

## Quick Start

```bash
# Backend
cd backend
cp .env.example .env   # then fill in MySQL password, SECRET_KEY, optional DEEPSEEK_API_KEY
pip install -r requirements.txt
python -m app.db.init_db
python -m app.db.seed_demo_data
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Demo accounts: `user_demo` (user), `user_demo2` (user), `admin_demo` (admin). Set the demo password with `DEMO_PASSWORD` or `ADMIN_DEMO_PASSWORD`, or run the seed script and read the generated password from the console output.

## Commands

```bash
# Backend tests — run all
cd backend && python -m unittest discover -s tests -p "test_*.py"

# Backend tests — run a single file
cd backend && python -m unittest tests.test_detect_api

# Syntax check critical files
cd backend && python -m py_compile app/db/seed_demo_data.py app/core/config.py app/main.py app/db/init_db.py

# Frontend build check
cd frontend && npm run build

# Lint git whitespace
git diff --check
```

## Architecture

### Backend Layering (strict, top-to-bottom)

```
api/v1/          → Request handling, auth checks, calls services. No business logic.
services/        → All business logic: detection pipeline, LLM calls, RAG, scoring.
crud/            → Pure database CRUD. No business rules.
models/          → SQLAlchemy ORM models (one per table).
schemas/         → Pydantic request/response schemas.
core/            → config.py (env vars), security.py (JWT/bcrypt), deps.py (DI),
                   constants.py (risk level thresholds), rate_limit.py.
db/              → session.py (engine), base.py (model registry), init_db.py, seed_demo_data.py.
utils/           → text_cleaner.py, risk_level.py, response.py, high_risk.py.
```

### Core Detection Pipeline (`services/detection_service.py`)

The central flow — `detect_news_credibility()`:

1. **Keyword extraction** — pattern-matches title+content against predefined word lists
2. **RAG evidence retrieval** — builds query text → searches Chroma for top-10 similar knowledge items → cross-verifies results against MySQL
3. **LLM analysis** — builds prompt from template + title + content + top-5 evidence → calls DeepSeek API → parses JSON response (with multiple fallback strategies)
4. **Rule-based scoring** — deducts points for exaggerated words, missing sources, emotional language, absolute claims, evidence conflicts
5. **Final score**: `evidence_score × 0.4 + llm_score × 0.4 + rule_score × 0.2`
6. **Risk level** thresholds (in `core/constants.py`): ≥80 trusted, ≥60 suspicious, ≥40 rumor, <40 high-risk

### Scoring System

- **LLM score** (0-100): DeepSeek analyzes credibility against evidence
- **Rule score** (0-100): starts at 100, deductions for linguistic red flags (exaggeration: -15, missing source: -20, emotional: -15, absolute terms: -15, evidence conflict: -25)
- **Evidence score** (0-100): average similarity of top-5 evidence items (cosine distance → percentage)
- **Final score**: weighted blend of the three above

### Embedding Strategy

Default embedding provider is `dashscope` with DashScope `text-embedding-v4` 1024-dimensional semantic embeddings for formal RAG and defense demos. `hash` remains available only as an explicit local demo fallback (`EMBEDDING_PROVIDER=hash`, `EMBEDDING_DIMENSION=384`) and does NOT encode meaning. After changing `EMBEDDING_PROVIDER` or `EMBEDDING_DIMENSION`, rebuild the Chroma knowledge index with `POST /api/admin/knowledge/rebuild-index` or reseed Chroma.

### Chroma Vector Store (`services/chroma_service.py`)

- Collection name: `knowledge_items`
- Distance metric: cosine
- Client/collection handles are cached in module-level dicts; operations retry once on failure (clearing cached handles)
- Knowledge CRUD in `services/knowledge_service.py` syncs MySQL ↔ Chroma: create/update writes both, delete removes Chroma first then MySQL (with restore-on-failure compensation)

### Authentication & Authorization

- JWT tokens (HS256), bcrypt password hashing
- `core/deps.py`: `get_current_user` (requires valid token), `get_current_admin` (requires `role == "admin"`), `get_optional_current_user` (allows anonymous)
- Token expiry: 1440 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- `SECRET_KEY` is validated at startup — rejects placeholder values and weak production keys

### Rate Limiting

In-memory sliding window via `core/rate_limit.py`. The `/api/detect` endpoint is rate-limited (default: 3 requests per 60 seconds, configurable via `DETECT_RATE_LIMIT_COUNT` and `DETECT_RATE_LIMIT_WINDOW_SECONDS`).

### Frontend Structure

```
src/
├── api/           → Axios wrappers per domain (auth.js, detect.js, report.js, etc.)
├── components/    → Reusable: ScoreCard, EvidenceList, AgentSteps, RiskLevelTag, etc.
├── components/admin/ → Admin-specific: AdminStatCard, AdminChartPanel, etc.
├── views/         → Page components under user/ and admin/ directories
├── layouts/       → UserLayout.vue (public + user), AdminLayout.vue (admin sidebar)
├── router/        → Vue Router with lazy loading, auth guards via beforeEach
├── stores/        → Pinia: user.js (auth state, session restore)
├── utils/         → request.js (axios instance with interceptors), format.js, auth.js
```

### Key Backend Files Reference

| File | Role |
|---|---|
| `app/main.py` | App factory, CORS, exception handlers |
| `app/api/router.py` | Single aggregation point for all v1 routers |
| `app/core/config.py` | All env var parsing, `Settings` class, `get_settings()` |
| `app/core/deps.py` | `get_current_user`, `get_current_admin` dependencies |
| `app/core/security.py` | JWT encode/decode, bcrypt hash/verify |
| `app/core/constants.py` | Risk level labels and score thresholds |
| `app/db/session.py` | SQLAlchemy engine, `get_db` generator |
| `app/db/base.py` | Model registry (`Base` + all model imports) |
| `app/services/detection_service.py` | Main detection pipeline |
| `app/services/llm_service.py` | DeepSeek API call, prompt building, JSON parsing |
| `app/services/chroma_service.py` | Chroma client/collection management, vector upsert/query/delete |
| `app/services/knowledge_service.py` | Knowledge CRUD with MySQL↔Chroma sync |
| `app/services/rule_score_service.py` | Linguistic rule-based scoring |
| `app/services/embedding_service.py` | Text → vector (DashScope semantic embedding, hash fallback) |

### Environment Variables

All in `backend/.env`. Two MySQL config modes: split fields (`DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME`) or a single `DATABASE_URL` (takes precedence). `CHROMA_PATH` sets vector store location. `REPORT_DIR` must point outside the backend source tree. `DEEPSEEK_API_KEY` is required for real LLM detection (demo seed works without it).

### Git-Ignored Paths

`backend/.env`, `data/reports/`, `data/chroma/`, `backend/chroma_db/`, `node_modules/`, `dist/`.

## Web Search & Scheduled Crawling (Bocha AI)

The system integrates **Bocha AI Web Search API** (`https://api.bocha.cn/v1/web-search`) for two
purposes:

### Real-Time Web Search During Detection

During news detection (`detect_news_credibility`), if the local Chroma RAG retrieval returns
insufficient evidence (top-1 similarity < 0.4, or < 0.6 with fewer than 3 results), the system
automatically triggers a Bocha web search to supplement the evidence pool.  Users can toggle this
behaviour off via the `enable_web_search` switch on the Detect page.

Key files:
- `services/web/bocha_client.py` — Bocha HTTP client (auth, retry, error classification)
- `services/web/web_search_service.py` — trigger logic, query building, evidence merging
- `services/detection_service.py` — integration point (RAG → web search → merged evidence → LLM)

### Scheduled News Crawling Into Knowledge Base

APScheduler runs a configurable cron job that periodically searches Bocha for news across 9
categories (社会, AI, 科技, 财经, 健康, 教育, 国际, 娱乐, 体育), fetches full article content,
deduplicates against the existing knowledge base, and ingests new entries with
`truth_label="待核查"` and `admin_note="[自动导入]"`.

Key files:
- `services/web/news_crawler.py` — crawl job definitions and execution logic
- `services/web/web_content_fetcher.py` — SSRF-safe HTML fetching + BeautifulSoup extraction
- `core/scheduler.py` — APScheduler lifecycle (startup/shutdown via FastAPI lifespan)
- `models/crawl_task.py` — execution log ORM model

### Configuration

```bash
BOCHA_API_KEY=sk-...           # required; from https://open.bochaai.com/
WEB_SEARCH_ENABLED=true        # global toggle for real-time search
CRAWL_ENABLED=true             # global toggle for scheduled crawling
CRAWL_SCHEDULE=0 */6 * * *     # cron expression
```
