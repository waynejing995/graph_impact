"""Document conversion helpers for ASIP corpus ingestion."""

from __future__ import annotations

import base64
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class DocumentChunk:
    source_path: str
    source_type: str
    page: int
    text: str


def convert_pdf_to_chunks(path: Path) -> List[DocumentChunk]:
    """Convert a text-based PDF into normalized chunks with page metadata.

    pypdf is preferred for page-preserving extraction. MarkItDown is used as a
    broad document conversion fallback when installed. The final fallback handles
    simple text-based PDFs used in deterministic tests and keeps the ingestion
    contract alive in minimal local environments.
    """

    pypdf_chunks = _try_pypdf(path)
    if pypdf_chunks:
        return pypdf_chunks

    markitdown_text = _try_markitdown(path)
    text = markitdown_text if markitdown_text else _extract_simple_pdf_text(path)
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []
    return [DocumentChunk(source_path=str(path), source_type="pdf", page=1, text=normalized)]


def _try_pypdf(path: Path) -> List[DocumentChunk]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return []

    try:
        reader = PdfReader(str(path))
    except Exception:
        return []

    chunks: List[DocumentChunk] = []
    for index, page in enumerate(getattr(reader, "pages", []), start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if normalized:
            chunks.append(DocumentChunk(source_path=str(path), source_type="pdf", page=index, text=normalized))
    return chunks


def _try_markitdown(path: Path) -> str:
    try:
        from markitdown import MarkItDown  # type: ignore
    except Exception:
        return ""

    try:
        result = MarkItDown().convert(str(path))
    except Exception:
        return ""
    return str(getattr(result, "text_content", "") or "")


def _extract_simple_pdf_text(path: Path) -> str:
    raw_bytes = path.read_bytes()
    raw = raw_bytes.decode("latin-1", errors="ignore")
    text_runs = _extract_pdf_text_runs(raw)
    for stream in _decode_pdf_streams(raw_bytes):
        text_runs.extend(_extract_pdf_text_runs(stream.decode("latin-1", errors="ignore")))
    return "\n".join(_unescape_pdf_string(item) for item in text_runs)


def _extract_pdf_text_runs(value: str) -> List[str]:
    text_runs = re.findall(r"\(([^()]*)\)\s*Tj", value)
    array_runs = re.findall(r"\[((?:\s*\([^()]*\)\s*)+)\]\s*TJ", value)
    for run in array_runs:
        text_runs.extend(re.findall(r"\(([^()]*)\)", run))
    return text_runs


def _decode_pdf_streams(raw: bytes) -> List[bytes]:
    decoded: List[bytes] = []
    stream_pattern = re.compile(br"<<(?P<dict>.*?)>>\s*stream\s*(?P<body>.*?)\s*endstream", re.S)
    for match in stream_pattern.finditer(raw):
        filters = match.group("dict")
        body = match.group("body").strip()
        if not body:
            continue
        try:
            if b"ASCII85Decode" in filters:
                if body.endswith(b"~>"):
                    body = body[:-2]
                body = base64.a85decode(body, adobe=False)
            if b"FlateDecode" in filters:
                body = zlib.decompress(body)
        except Exception:
            continue
        decoded.append(body)
    return decoded


def _unescape_pdf_string(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )
