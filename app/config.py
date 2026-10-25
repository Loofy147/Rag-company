from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str = "postgresql+psycopg://rag:change-me@db:5432/rag"
    jwt_secret: str = ""
    jwt_issuer: str = "vaultrag-local"
    jwt_ttl_minutes: int = 30
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = ""
    ollama_base_url: str = "http://ollama:11434"
    chat_model: str = "qwen2.5:3b"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    max_upload_bytes: int = 20 * 1024 * 1024
    retrieval_top_k: int = 6
    rrf_candidates: int = 24
    rrf_k: int = 60
    max_chunk_chars: int = 1800
    chunk_overlap_chars: int = 220
    enable_api_docs: bool = False


settings = Settings()


def validate_security_settings() -> None:
    if len(settings.jwt_secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 bytes.")
    if settings.max_upload_bytes < 1024:
        raise RuntimeError("MAX_UPLOAD_BYTES must be at least 1024.")
    if settings.embedding_dimensions != 768:
        raise RuntimeError("The schema uses 768-dimensional vectors; review migration before changing.")
    if not 5 <= settings.jwt_ttl_minutes <= 240:
        raise RuntimeError("JWT_TTL_MINUTES must be between 5 and 240.")
