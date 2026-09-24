FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY backend/requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY backend/ .
COPY contracts/ /app/contracts/
COPY evaluation/__init__.py /app/evaluation/__init__.py
COPY evaluation/ai_engineering/ /app/evaluation/ai_engineering/
COPY scripts/ci/verify_runtime_package.py /app/verify_runtime_package.py

RUN PYTHON_DOTENV_DISABLED=1 SECRET_KEY=build-smoke-secret-0123456789abcdef \
    EMBEDDING_PROVIDER=hash WEB_SEARCH_ENABLED=false CRAWL_ENABLED=false \
    REDIS_ENABLED=false PYROSCOPE_ENABLED=false \
    python /app/verify_runtime_package.py

RUN mkdir -p /data/chroma /data/reports \
    && chown -R app:app /app /data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=3).read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
