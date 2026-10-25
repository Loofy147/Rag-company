# Production-readiness roadmap

Statuses: IN SOURCE, VERIFIED IN TARGET ENVIRONMENT, OPEN, ACCEPTED RESIDUAL RISK.

## Baseline
- [x] FastAPI + Docling + Ollama + PostgreSQL/pgvector composition.
- [x] Loopback API and internal runtime network.
- [x] Argon2 authentication, short-lived JWT and role/group checks.
- [x] SQL-side visibility filters on both retrieval paths.
- [x] Vector and full-text retrieval fused with Reciprocal Rank Fusion.
- [x] Citation-ID validation and abstention on incomplete coverage.
- [x] Metadata-only audit, bounded uploads and temporary raw-file handling.
- [x] Unit tests and CI workflow.

## Retrieval and answer quality
- [ ] Version a golden set with expected source locations, factual claims, no-answer and multilingual cases.
- [ ] Measure Recall@k, MRR/nDCG, citation precision, relevance, faithfulness and abstention accuracy separately.
- [ ] Add hostile fixtures for prompt injection, hidden text, conflicts, citation spoofing and split payloads.
- [ ] Tie regression thresholds to measured baselines and report uncertainty.
- [ ] Preserve page/cell provenance and render precise source locators.

## Identity and lifecycle
- [ ] Integrate OIDC/LDAP/AD and trusted group mapping.
- [ ] Add account disablement, role/group changes, token revocation and credential rotation.
- [ ] Add versioned migrations, document versions, retention and audited purge.
- [ ] Add malware quarantine and a sandboxed ingestion worker with CPU, memory and time limits.
- [ ] Add recoverable async jobs, retries and idempotency.
- [ ] Test encrypted backup, restore, deletion and retention.

## Operations
- [ ] Pin images and dependency hashes; generate SBOM and vulnerability reports.
- [ ] Add shared rate limiting, model queues, concurrency budgets, redacted metrics and SLOs.
- [ ] Benchmark HNSW filtering, recall, latency, memory and target hardware.
- [ ] Add automated migration, rollback and restore tests.
- [ ] Conduct an independent security review.

## Deployment acceptance
- [ ] Prove no external egress during chat and ingestion for each required file type.
- [ ] Run ACL regression tests against real PostgreSQL with overlapping/disjoint groups.
- [ ] Run parser sandbox review and adversarial RAG tests.
- [ ] Verify logs, firewall, secrets, encryption, backup and retention.
- [ ] Record residual-risk owners and approve release gates.

Do not label this production-ready until required target-environment evidence exists.
