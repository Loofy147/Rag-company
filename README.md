# Rag-company — VaultRAG

A local-first private knowledge workspace for internal documents. It combines Docling parsing, local Ollama inference, PostgreSQL/pgvector retrieval, authorization-aware hybrid search and citation-gated answers.

**Deployment boundary:** designed for an organization's own host. Do not deploy confidential document processing to a hosted preview or upload private data before completing local-only and access-control acceptance tests.

## Included
- FastAPI, Argon2 password hashes and short-lived JWTs.
- Admin, contributor and reader roles; private, workspace and assigned-group visibility.
- PDF, DOCX, XLSX, HTML, Markdown, TXT and CSV ingestion.
- PostgreSQL/pgvector vector search plus full-text retrieval fused with Reciprocal Rank Fusion.
- Database-side authorization filters before either retrieval path.
- Citation IDs checked against the current retrieval set; incomplete citation coverage is withheld.
- Metadata-only audit events; raw prompts, answers and excerpts are not written to audit records.
- Loopback-bound API and internal runtime network.

## Local setup
Copy .env.example to .env. Generate separate URL-safe secrets with `openssl rand -hex 32` for `DB_ADMIN_PASSWORD`, `RAG_DB_PASSWORD` and `JWT_SECRET`. Keep the password in `DATABASE_URL` identical to `RAG_DB_PASSWORD`. `DB_ADMIN_PASSWORD` is used only by PostgreSQL initialization and is not passed to the API container. The bootstrap admin password must be unique and at least 12 characters. Start the provisioning stack with `docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml up -d --build`, then run `docker compose exec ollama ollama pull qwen2.5:3b` and `docker compose exec ollama ollama pull nomic-embed-text`. Sign in at http://127.0.0.1:8080 and exercise each required file type with synthetic files to warm parser assets. Then run `docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml down` followed by `docker compose -f docker-compose.yml up -d --build`. Do not use `down -v` for a database containing data. If the first PostgreSQL initialization fails after the data directory is created, init scripts will not automatically rerun; remove only a confirmed disposable empty volume before retrying—never delete a volume containing data.

The bootstrap network is for provisioning only. The PostgreSQL init script creates the `rag_app` runtime role and runs only when the database volume is first initialized. The API is not given the `rag_admin` secret. If initialization fails on a disposable new volume, correct the configuration before retrying; do not delete a volume that contains data. Prove that chat and ingestion work with outbound egress denied before importing confidential documents.

## Development checks
Install requirements-dev.txt and run Python compilation, Ruff and pytest. Unit tests cover pure helper behavior; they do not establish live PostgreSQL authorization, Ollama/Docling correctness, browser behavior or network isolation.

## Limitations
Original uploads are handled temporarily; extracted text and embeddings persist in PostgreSQL. Citation-ID checks do not prove entailment. Login throttling is process-local. Parsing currently runs in the API process. OIDC, malware quarantine, versioned migrations, tamper-evident audit, encrypted backup/restore and independent security testing remain open.

See docs/THREAT_MODEL.md and docs/ROADMAP.md. Do not label the project production-ready until target-environment acceptance evidence exists.
