# Threat model

## Assets
Source documents, extracted text, embeddings, prompts, answers, account/group mappings, database credentials, JWT secret and audit records.

## Trust boundaries
1. Browser to FastAPI: document, chat and admin operations require an active bearer token.
2. FastAPI to PostgreSQL: ACL predicates must be applied before retrieval ranking and context construction.
3. FastAPI to Ollama: local-model requests use a private network address and disable inherited HTTP proxy settings.
4. Uploaded files to Docling: parsers process untrusted files and need resource isolation.
5. Bootstrap provisioning to runtime: outbound access is temporarily enabled to fetch assets and must be disabled before confidential documents are loaded.

## Threats and controls
| Threat | Current control | Residual risk |
|---|---|---|
| Unauthorized document retrieval | SQL-side visibility predicates on vector and lexical paths | Requires live multi-account DB tests |
| Prompt injection | Excerpts labelled untrusted; no tools are exposed to the model | Model can still be manipulated |
| Forged citations | IDs checked against the retrieved source set | Does not prove entailment |
| Brute force | Argon2 hashes and process-local throttling | Not shared across workers |
| Oversized upload | Byte and chunk-count limits | Parser time/memory not isolated |
| Browser script injection | DOM text APIs and same-origin CSP | Reassess if HTML rendering is introduced |
| Remote parser fetch | HTML/Markdown resource references stripped | Runtime egress must be verified |
| Sensitive errors | Validation input excluded; parser/model errors sanitized | Review host/access logs separately |
| Cloud inference leakage | Local Ollama, internal network, API bound to loopback | Prove actual egress denial empirically |

This is not a security certification. OIDC, malware quarantine, sandboxed ingestion worker, shared rate limiting, migration controls, tamper-evident audit, encrypted backups and independent penetration testing remain open.

Use synthetic data first. Preserve reproducible ACL tests, hostile document fixtures, egress observations, backup/restore evidence and the exact software/model versions tested.
