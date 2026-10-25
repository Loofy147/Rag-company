from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from app.config import settings
from app.core import chunk_markdown, sanitize_markdown_resource_targets


class IngestionError(Exception):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_html(path: Path) -> None:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "iframe", "object", "embed", "form", "svg", "video", "audio", "link", "meta", "base"]):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in ("src", "srcset", "action", "formaction", "poster", "data", "style"):
            tag.attrs.pop(attr, None)
        for attr in ("href", "xlink:href"):
            value = str(tag.get(attr, "")).strip()
            if value and not value.startswith("#"):
                tag.attrs.pop(attr, None)
        for attr in list(tag.attrs):
            if attr.lower().startswith("on"):
                tag.attrs.pop(attr, None)
    path.write_text(str(soup), encoding="utf-8")


def parse_document(filename: str, data: bytes) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".xlsx", ".html", ".htm", ".md", ".markdown", ".txt", ".csv"}:
        raise IngestionError("unsupported_file_type")
    if not data:
        raise IngestionError("empty_file")
    try:
        from docling.document_converter import DocumentConverter

        with tempfile.TemporaryDirectory(prefix="vaultrag-") as directory:
            path = Path(directory) / ("input" + suffix)
            path.write_bytes(data)
            if suffix in {".html", ".htm"}:
                sanitize_html(path)
            elif suffix in {".md", ".markdown"}:
                path.write_text(sanitize_markdown_resource_targets(path.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
            markdown = DocumentConverter().convert(str(path)).document.export_to_markdown()
            chunks = chunk_markdown(markdown, settings.max_chunk_chars, settings.chunk_overlap_chars)
            if not chunks:
                raise IngestionError("no_extractable_text")
            return chunks
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError("document_parse_failed") from exc
