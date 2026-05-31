from __future__ import annotations

import zipfile
import re
from html import unescape
from pathlib import Path

from ..models import ContentInput


TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".text"}
DOCX_EXTENSIONS = {".docx"}


def load_content_from_file(
    path: Path,
    source: str,
    platform: str = "local",
    kind: str = "artifact",
    entity: str | None = None,
    profile: str | None = None,
    purpose: str | None = None,
    title: str | None = None,
) -> ContentInput:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        text = path.read_text(encoding="utf-8").strip()
    elif suffix in DOCX_EXTENSIONS:
        text = extract_docx_text(path).strip()
    else:
        raise ValueError(f"Unsupported file type for text import: {path.suffix}")

    if not text:
        raise ValueError(f"File is empty: {path}")

    return ContentInput(
        source=source,
        platform=platform,
        kind=kind,
        entity=entity,
        profile=profile or "unknown",
        purpose=purpose or "general",
        title=title or path.stem,
        content_id=f"file:{path.resolve()}",
        canonical_key=f"file:{path.resolve()}",
        url=str(path.resolve()),
        text=text,
        metadata={"file_path": str(path.resolve()), "file_type": suffix.lstrip(".")},
    )


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")

    paragraphs: list[str] = []
    for paragraph_xml in re.findall(r"<w:p\b[^>]*>(.*?)</w:p>", document_xml, flags=re.DOTALL):
        chunks: list[str] = []
        tokens = re.findall(
            r"(<w:t\b[^>]*>.*?</w:t>|<w:tab\b[^>]*/>|<w:br\b[^>]*/>)",
            paragraph_xml,
            flags=re.DOTALL,
        )
        for token in tokens:
            if token.startswith("<w:t"):
                match = re.search(r"<w:t\b[^>]*>(.*?)</w:t>", token, flags=re.DOTALL)
                if match:
                    chunks.append(unescape(re.sub(r"<[^>]+>", "", match.group(1))))
            elif token.startswith("<w:tab"):
                chunks.append("\t")
            elif token.startswith("<w:br"):
                chunks.append("\n")
        text = "".join(chunks).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)
