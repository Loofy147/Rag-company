# Pre-configuration baseline

Status labels: **ESTABLISHED** = supported by repository state or current upstream documentation; **OPEN** = must be checked in the target runtime; **BLOCKING** = do not import confidential data until evidence is recorded.

This document records the configuration baseline before live deployment work. It is not a production-readiness certificate.

## 1. Framework and lifecycle

- [x] **ESTABLISHED** — FastAPI startup initialization uses the recommended `lifespan` async context manager rather than deprecated startup event hooks.
- [x] **ESTABLISHED** — Configuration is read from environment-backed typed settings; example values are placeholders, not deployable credentials.
- [ ] **OPEN** — Verify startup and shutdown behavior with the exact pinned dependency set and a real database connection.
- [ ] **OPEN** — Ensure readiness reports dependency state separately from liveness; a running HTTP process alone does not prove retrieval is ready.

Reference: [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/), [FastAPI settings](https://fastapi.tiangolo.com/advanced/settings/).

## 2. Compose and network boundary

- [x] **ESTABLISHED** — The API is published on loopback by default; database and Ollama are placed on the internal Compose network.
- [x] **ESTABLISHED** — PostgreSQL has a health check and the API waits for the database health condition.
- [ ] **OPEN** — Validate the resolved configuration using the actual deployment `.env` without printing secret values into CI logs or issue comments.
- [ ] **OPEN** — Prove outbound egress is denied from the application runtime while required local service-to-service traffic still works. An `internal: true` Compose network is a configuration signal, not a substitute for host-level network verification.
- [ ] **OPEN** — Pin container images to reviewed versions or digests before a production release; do not treat floating tags as reproducible.
- [ ] **OPEN** — Define resource limits, restart behavior, backup/restore, log retention and update/rollback procedures for the target host.

Reference: [Docker Compose documentation](https://docs.docker.com/compose/).

## 3. Credentials and configuration

- [x] **ESTABLISHED** — PostgreSQL bootstrap administrator credentials are separate from the application runtime database role.
- [x] **ESTABLISHED** — Startup validation rejects known placeholder/weak database secrets.
- [ ] **OPEN** — Generate unique deployment secrets locally; never commit `.env`, model cache data, user documents or real tokens.
- [ ] **OPEN** — Decide whether the target deployment will use a secret manager or mounted secret files rather than environment variables for long-lived secrets.
- [ ] **OPEN** — Confirm password rotation, JWT secret rotation/revocation and administrator recovery procedures.
- [ ] **OPEN** — Confirm a fresh database volume and an existing database volume both behave safely. PostgreSQL initialization scripts run only on first initialization of an empty data directory; never delete a non-disposable volume to retry initialization.

## 4. Database and schema

- [x] **ESTABLISHED** — SQLAlchemy schema includes a functional lower-case username uniqueness index, matching normalized usernames.
- [ ] **OPEN** — Test PostgreSQL/pgvector extension creation and application-role grants using the exact image and role configuration.
- [ ] **OPEN** — Introduce and verify explicit, versioned schema migrations before treating upgrades as production-safe. ORM metadata creation alone is not a migration/rollback strategy.
- [ ] **OPEN** — Test backup and restore of documents, embeddings, accounts, groups and audit metadata; document recovery-point and recovery-time objectives.
- [ ] **OPEN** — Run concurrent retrieval and ingestion tests against the target PostgreSQL instance.

Reference: [SQLAlchemy Index documentation](https://docs.sqlalchemy.org/en/20/core/constraints.html#sqlalchemy.schema.Index), [SQLAlchemy session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).

## 5. RAG and document handling

- [ ] **OPEN** — Pin and record chat and embedding model identifiers, versions/digests where available, and embedding dimensions.
- [ ] **OPEN** — Test all advertised document formats with synthetic fixtures, including malformed files, oversized files, empty documents and parser timeouts.
- [ ] **OPEN** — Confirm retrieval ACL predicates apply before results reach the model for both vector and lexical paths.
- [ ] **OPEN** — Test indirect prompt injection in documents, cross-user retrieval attempts, fabricated citations and unsupported-answer behavior.
- [ ] **OPEN** — Record a baseline evaluation set: retrieval recall/precision, citation correctness, answer faithfulness, latency, memory use and ingestion failures.
- [ ] **BLOCKING** — Do not import confidential documents until egress denial, access-control isolation and backup/restore have evidence.

## 6. Release evidence package

For every target-host test, record:

1. commit SHA and container image identifiers;
2. exact non-secret configuration fingerprint;
3. test procedure and synthetic fixture identifiers;
4. expected versus actual result;
5. logs/metrics with secrets and document contents redacted;
6. pass/fail, scope, limitations and remaining uncertainty;
7. rollback or recovery result.

## Acceptance gate

A green unit/CI run establishes source and configuration checks only. Mark this baseline production-ready only after the open runtime checks above are completed and independently re-checked. Do not silently promote **OPEN** to **VERIFIED** based on a code review or a Compose parse.
