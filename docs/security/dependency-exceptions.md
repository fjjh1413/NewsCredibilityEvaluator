# Dependency Vulnerability Exceptions

Every exception must have an owner, a reason, and a review date. Remove the
exception as soon as an upstream fix is available.

| Package | Advisory | Status | Owner | Review Date | Rationale |
| --- | --- | --- | --- | --- | --- |
| `chromadb` | `PYSEC-2026-311` / `CVE-2026-45829` | Temporary exception | Backend maintainers | 2026-08-06 | `pip-audit` reports ChromaDB `1.5.9` as affected and does not list a fixed version. This project uses `chromadb.PersistentClient` with a local `CHROMA_PERSIST_DIR` volume and does not run or expose the ChromaDB Python FastAPI server. Production deployments must keep Chroma data local to the backend container and must not publish a Chroma HTTP port. Remove this exception as soon as upstream publishes a fixed release. |
