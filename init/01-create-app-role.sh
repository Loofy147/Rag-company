#!/usr/bin/env bash
set -Eeuo pipefail
: "${RAG_DB_USER:?RAG_DB_USER must be set}"
: "${RAG_DB_PASSWORD:?RAG_DB_PASSWORD must be set}"
for name in POSTGRES_PASSWORD RAG_DB_PASSWORD; do
  value="${!name}"
  normalized="${value,,}"
  if [[ ${#value} -lt 32 || "$normalized" == *replace-with* || "$normalized" == *change-me* || "$normalized" == *changeme* ]]; then
    printf "Refusing to initialize PostgreSQL with an example or weak %s.\n" "$name" >&2
    exit 1
  fi
done
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_user="$RAG_DB_USER" --set=app_password="$RAG_DB_PASSWORD" \
  --set=app_database="$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';
GRANT CONNECT ON DATABASE :"app_database" TO :"app_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
ALTER SCHEMA public OWNER TO :"app_user";
SQL
