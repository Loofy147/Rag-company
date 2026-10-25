from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings, validate_security_settings
from app.core import GROUP_PATTERN, allowed_extension, can_share_document, safe_display_filename
from app.db import SessionLocal, engine, get_db, initialize_database
from app.ingestion import IngestionError, parse_document, sha256_bytes
from app.models import AuditEvent, Chunk, Document, User
from app.rag import ModelUnavailable, answer_question, document_visibility_filter, embed_texts
from app.security import bootstrap_admin, hash_password, issue_access_token, resolve_token, verify_password

STATIC_DIR = Path(__file__).parent / "static"
bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="VaultRAG Private Knowledge Workspace", version="0.1.0", docs_url="/docs" if settings.enable_api_docs else None, redoc_url=None, openapi_url="/openapi.json" if settings.enable_api_docs else None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
attempts: defaultdict[str, deque[float]] = defaultdict(deque)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.@-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "contributor", "reader"] = "reader"
    groups: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("groups")
    @classmethod
    def clean_groups(cls, groups: list[str]) -> list[str]:
        items = sorted({item.strip() for item in groups if item and item.strip()})
        if any(not GROUP_PATTERN.fullmatch(item) for item in items):
            raise ValueError("Invalid group name.")
        return items


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def nonblank(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("Question cannot be blank.")
        return question.strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    role: str
    groups: list[str]
    is_active: bool
    created_at: datetime


def audit(db: Session, actor_id: UUID | None, action: str, entity_type: str, entity_id: str | None = None, outcome: str = "success", metadata: dict | None = None) -> None:
    db.add(AuditEvent(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, outcome=outcome, metadata_json=metadata or {}))


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = resolve_token(credentials.credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")
    return user


def require_role(*roles: str):
    def guard(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Permission denied.")
        return user
    return guard


def login_limited(key: str) -> bool:
    now = time.monotonic()
    window = attempts[key]
    while window and now - window[0] > 900:
        window.popleft()
    return len(window) >= 8


@app.on_event("startup")
def startup() -> None:
    validate_security_settings()
    initialize_database()
    with SessionLocal() as db:
        bootstrap_admin(db)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    safe = [{"loc": [str(part) for part in item.get("loc", ())], "msg": str(item.get("msg", "Invalid request")), "type": str(item.get("type", "value_error"))} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": safe})


@app.exception_handler(ModelUnavailable)
async def model_unavailable(_request: Request, _exc: ModelUnavailable):
    return JSONResponse(status_code=503, content={"detail": "Local model service unavailable; check model readiness."})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> JSONResponse:
    database, model = "ok", "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        database = "unavailable"
    try:
        with httpx.Client(timeout=2.5, trust_env=False) as client:
            response = client.get(settings.ollama_base_url.rstrip("/") + "/api/tags")
            response.raise_for_status()
    except Exception:
        model = "unavailable"
    ready = database == model == "ok"
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ok" if ready else "degraded", "database": database, "local_model": model})


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    key = request.client.host if request.client else "unknown"
    if login_limited(key):
        raise HTTPException(status_code=429, detail="Too many login attempts; retry in 15 minutes.")
    user = db.query(User).filter(func.lower(User.username) == payload.username.strip().lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        attempts[key].append(time.monotonic())
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    attempts.pop(key, None)
    audit(db, user.id, "auth.login", "session", metadata={"method": "password"})
    db.commit()
    return {"access_token": issue_access_token(user), "token_type": "bearer", "expires_in": settings.jwt_ttl_minutes * 60}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@app.get("/api/metrics")
def metrics(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    visible = document_visibility_filter(user)
    indexed = db.scalar(select(func.count(Document.id)).where(visible, Document.state == "indexed")) or 0
    failed = db.scalar(select(func.count(Document.id)).where(visible, Document.state == "failed")) or 0
    chunks = db.scalar(select(func.count(Chunk.id)).join(Document).where(visible, Document.state == "indexed")) or 0
    result = {"indexed_documents": int(indexed), "failed_documents": int(failed), "indexed_chunks": int(chunks), "role": user.role, "groups": user.groups}
    if user.role == "admin":
        result["active_users"] = int(db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0)
    return result


@app.get("/api/documents")
def list_documents(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Document).where(document_visibility_filter(user)).order_by(Document.created_at.desc()).limit(500)).all()
    return [{"id": str(d.id), "filename": d.filename, "state": d.state, "error_code": d.error_code, "visibility": d.visibility, "allowed_groups": d.allowed_groups, "chunk_count": d.chunk_count, "size_bytes": d.size_bytes, "created_at": d.created_at.isoformat(), "indexed_at": d.indexed_at.isoformat() if d.indexed_at else None, "can_delete": user.role == "admin" or d.owner_id == user.id} for d in rows]


@app.post("/api/documents", status_code=201)
def upload_document(file: UploadFile = File(...), visibility: str = Form("private"), groups_csv: str = Form(""), user: User = Depends(require_role("admin", "contributor")), db: Session = Depends(get_db)) -> dict:
    filename = safe_display_filename(file.filename or "uploaded-document")
    if not allowed_extension(filename):
        raise HTTPException(status_code=415, detail="Unsupported file extension.")
    if visibility not in {"private", "workspace", "groups"}:
        raise HTTPException(status_code=422, detail="Invalid visibility.")
    groups = sorted({value.strip() for value in groups_csv.split(",") if value.strip()})
    if len(groups) > 50 or any(not GROUP_PATTERN.fullmatch(value) for value in groups):
        raise HTTPException(status_code=422, detail="Invalid group names.")
    if visibility == "groups" and not groups:
        raise HTTPException(status_code=422, detail="Group visibility requires a group.")
    if not can_share_document(user_role=user.role, user_groups=user.groups, visibility=visibility, allowed_groups=groups):
        raise HTTPException(status_code=403, detail="Workspace-wide sharing is admin-only; group sharing must use assigned groups.")
    raw = file.file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds configured size limit.")
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file.")
    digest = sha256_bytes(raw)
    if db.query(Document).filter(Document.owner_id == user.id, Document.sha256 == digest).first():
        raise HTTPException(status_code=409, detail="Identical upload already exists for this owner.")
    doc = Document(filename=filename, sha256=digest, size_bytes=len(raw), state="processing", owner_id=user.id, visibility=visibility, allowed_groups=groups)
    db.add(doc)
    db.commit()
    doc_id = doc.id
    try:
        chunks = parse_document(filename, raw)
        if len(chunks) > 2500:
            raise IngestionError("document_chunk_limit_exceeded")
        embeddings = embed_texts([chunk["content"] for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ModelUnavailable("Embedding count mismatch.")
        db.add_all([Chunk(document_id=doc_id, ordinal=i, content=chunk["content"], section=chunk["section"], page_start=chunk.get("page_start"), embedding=vector) for i, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=True), 1)])
        doc.state = "indexed"
        doc.chunk_count = len(chunks)
        doc.indexed_at = datetime.now(UTC)
        audit(db, user.id, "document.indexed", "document", str(doc_id), metadata={"chunks": len(chunks), "size_bytes": len(raw), "visibility": visibility})
        db.commit()
    except Exception as exc:
        db.rollback()
        failed = db.get(Document, doc_id)
        if failed:
            failed.state = "failed"
            failed.error_code = exc.args[0] if isinstance(exc, IngestionError) and exc.args else "indexing_failed"
            audit(db, user.id, "document.index_failed", "document", str(doc_id), outcome="failure", metadata={"reason_code": failed.error_code})
            db.commit()
        if isinstance(exc, IngestionError):
            raise HTTPException(status_code=422, detail="Document parsing failed.") from exc
        raise HTTPException(status_code=503, detail="Local ingestion service failed; check readiness.") from exc
    return {"id": str(doc_id), "filename": filename, "state": doc.state, "chunk_count": doc.chunk_count}


@app.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    doc = db.get(Document, document_id)
    if not doc or (user.role != "admin" and doc.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(doc)
    audit(db, user.id, "document.deleted", "document", str(document_id))
    db.commit()
    return Response(status_code=204)


@app.post("/api/chat")
def chat(payload: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = answer_question(db, user, payload.question)
    audit(db, user.id, "chat.completed", "query", metadata={"retrieved_count": result.get("retrieved_count", 0), "citation_validation": result.get("citation_validation", "not_applicable")})
    db.commit()
    return result


@app.get("/api/admin/users", response_model=list[UserOut])
def list_users(_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc()).limit(500)).all())


@app.post("/api/admin/users", status_code=201, response_model=UserOut)
def create_user(payload: UserCreate, actor: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> User:
    try:
        user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role, groups=payload.groups)
        db.add(user)
        db.flush()
        audit(db, actor.id, "user.created", "user", str(user.id), metadata={"role": user.role, "groups": user.groups})
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists.") from exc


@app.get("/api/audit")
def list_audit(limit: int = Query(default=100, ge=1, le=500), _user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> list[dict]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id": str(e.id), "actor_id": str(e.actor_id) if e.actor_id else None, "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id, "outcome": e.outcome, "metadata": e.metadata_json, "created_at": e.created_at.isoformat()} for e in events]
