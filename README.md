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
Copy .env.example to .env. Set a unique database password, a random JWT secret of at least 32 bytes and an admin password of at least 12 characters. Before loading private documents, temporarily enable the bootstrap network, pull the configured Ollama models and exercise each required file type using synthetic files. Stop the bootstrap stack and restart with the normal compose file. Open http://127.0.0.1:8080.

The bootstrap network is for provisioning only. Prove that chat and ingestion continue working with outbound egress denied before importing confidential documents.

## Development checks
Install requirements-dev.txt and run Python compilation, Ruff and pytest. Unit tests cover pure helper behavior; they do not establish live PostgreSQL authorization, Ollama/Docling correctness, browser behavior or network isolation.

## Limitations
Original uploads are handled temporarily; extracted text and embeddings persist in PostgreSQL. Citation-ID checks do not prove entailment. Login throttling is process-local. Parsing currently runs in the API process. OIDC, malware quarantine, versioned migrations, tamper-evident audit, encrypted backup/restore and independent security testing remain open.

See docs/THREAT_MODEL.md and docs/ROADMAP.md. Do not label the project production-ready until target-environment acceptance evidence exists.
