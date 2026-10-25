from __future__ import annotations

import re
from collections import defaultdict
from pathlib import PurePath
from typing import Any

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".html", ".htm", ".md", ".markdown", ".txt", ".csv"}
CITATION_PATTERN = re.compile(r"\[(S\d{1,3})\]")
HEADING_PATTERN = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
GROUP_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def allowed_extension(filename: str) -> bool:
    return PurePath(filename.replace("\\", "/").split("/")[-1]).suffix.lower() in ALLOWED_EXTENSIONS


def safe_display_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/").split("/")[-1]).name
    return re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:240] or "uploaded-document"


def can_share_document(*, user_role: str, user_groups: list[str], visibility: str, allowed_groups: list[str]) -> bool:
    if visibility == "private":
        return True
    if user_role == "admin":
        return visibility in {"workspace", "groups"} and (visibility != "groups" or bool(allowed_groups))
    return visibility == "groups" and bool(allowed_groups) and set(allowed_groups).issubset(set(user_groups))


def chunk_markdown(text: str, max_chars: int = 1800, overlap_chars: int = 220) -> list[dict[str, Any]]:
    if max_chars < 256:
        raise ValueError("max_chars must be at least 256")
    overlap_chars = max(0, min(overlap_chars, max_chars // 2))
    text = text.replace("\x00", " ").strip()
    if not text:
        return []
    blocks: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    section = "Document"
    current: list[str] = []

    def flush() -> None:
        value = "\n".join(current).strip()
        if value:
            blocks.append((section, value))
        current.clear()

    for line in text.splitlines():
        match = HEADING_PATTERN.match(line)
        if match:
            flush()
            level, heading = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            section = " / ".join(value for _, value in stack) or "Document"
            blocks.append((section, heading))
        elif line.strip():
            current.append(line)
        else:
            flush()
    flush()
    result: list[dict[str, Any]] = []

    def emit(value: str, name: str) -> None:
        if value.strip():
            result.append({"content": value.strip(), "section": name, "page_start": None})

    def windows(value: str, name: str) -> None:
        start = 0
        while start < len(value):
            end = min(start + max_chars, len(value))
            if end < len(value):
                boundary = value.rfind(" ", start + max_chars // 2, end)
                if boundary > start:
                    end = boundary
            emit(value[start:end], name)
            if end == len(value):
                break
            start = max(start + 1, end - overlap_chars)

    pending, pending_section = "", "Document"
    for name, block in blocks:
        table = [line for line in block.splitlines() if line.strip()]
        if len(block) > max_chars:
            if pending:
                emit(pending, pending_section)
                pending = ""
            if table and all(line.lstrip().startswith("|") for line in table):
                header = table[:2] if len(table) > 1 else table[:1]
                batch: list[str] = []
                for row in table[len(header):]:
                    if batch and len("\n".join(header + batch + [row])) > max_chars:
                        emit("\n".join(header + batch), name)
                        batch = []
                    if len("\n".join(header + [row])) > max_chars:
                        windows(row, name)
                    else:
                        batch.append(row)
                if batch:
                    emit("\n".join(header + batch), name)
            else:
                windows(block, name)
            continue
        candidate = (pending + "\n\n" + block).strip() if pending and pending_section == name else block
        if pending and (pending_section != name or len(candidate) > max_chars):
            emit(pending, pending_section)
            pending, pending_section = block, name
        else:
            pending, pending_section = candidate, name
    if pending:
        emit(pending, pending_section)
    return result


def reciprocal_rank_fusion(ranked_lists: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    scores: defaultdict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            key = str(item["id"])
            scores[key] += 1.0 / (k + rank)
            by_id.setdefault(key, dict(item))
    return sorted([{**by_id[key], "rrf_score": score} for key, score in scores.items()], key=lambda row: row["rrf_score"], reverse=True)


def retain_valid_citations(answer: str, valid_source_ids: set[str]) -> tuple[str, list[str]]:
    found = CITATION_PATTERN.findall(answer)
    valid = sorted({item for item in found if item in valid_source_ids})
    cleaned = CITATION_PATTERN.sub(lambda m: m.group(0) if m.group(1) in valid_source_ids else "", answer)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip(), valid


def has_complete_citation_coverage(answer: str, valid_source_ids: set[str]) -> bool:
    checked = 0
    for paragraph in [part.strip() for part in re.split(r"\n\s*\n", answer) if part.strip()]:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        is_list = any(re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", line) for line in lines)
        for unit in (lines if is_list else [paragraph]):
            if re.match(r"^\s{0,3}#{1,6}\s+", unit):
                continue
            plain = re.sub(r"[\x60*_>~-]", "", unit).strip()
            if len(re.findall(r"\w+", plain)) < 2:
                continue
            checked += 1
            if not set(CITATION_PATTERN.findall(unit)).intersection(valid_source_ids):
                return False
    return checked > 0


def sanitize_markdown_resource_targets(content: str) -> str:
    content = re.sub(r"!\[[^\]]*\](?:\([^)]*\)|\s*\[[^\]]*\])?", "", content)
    content = re.sub(r"(?m)^\s*\[[^\]]+\]:\s*\S+.*$", "", content)
    content = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", content)
    content = re.sub(r"(?is)<(script|style|iframe|object|embed|svg|video|audio|link|base)\b[^>]*>.*?</\1\s*>", "", content)
    return re.sub(r"(?is)<(?:img|iframe|object|embed|svg|video|audio|link|base)\b[^>]*?/?>", "", content)
