from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class ContentInput:
    source: str
    text: str
    platform: str = "x"
    kind: str = "post"
    entity: str | None = None
    profile: str = "unknown"
    purpose: str = "general"
    title: str | None = None
    content_id: str | None = None
    canonical_key: str | None = None
    url: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_id(self) -> str:
        if self.content_id:
            return self.content_id
        seed = "|".join(
            [
                self.platform,
                self.source,
                self.kind,
                self.created_at or "",
                self.url or "",
                self.title or "",
                self.text,
            ]
        )
        return sha256(seed.encode("utf-8")).hexdigest()[:20]

    def normalized_canonical_key(self) -> str:
        if self.canonical_key:
            return self.canonical_key
        platform = self.platform.strip().lower() or "unknown"
        if self.url:
            seed = f"{platform}|url|{self.url.strip()}"
        elif self.content_id:
            seed = f"{platform}|id|{self.content_id.strip()}"
        elif self.title:
            seed = f"{platform}|title|{self.source.strip()}|{self.title.strip()}"
        else:
            seed = f"{platform}|text|{self.source.strip()}|{self.text.strip()}"
        return sha256(seed.encode("utf-8")).hexdigest()[:32]

    def normalized_created_at(self) -> str:
        if not self.created_at:
            return datetime.now(timezone.utc).isoformat()
        value = self.created_at.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(value).isoformat()
        except ValueError:
            return value


@dataclass(frozen=True)
class StoredContent:
    content_id: str
    canonical_key: str
    platform: str
    source: str
    kind: str
    entity: str | None
    profile: str
    purpose: str
    title: str | None
    text: str
    url: str | None
    created_at: str
    updated_at: str | None
    metadata_json: str


# Backward-compatible aliases for the first X-only prototype.
PostInput = ContentInput
StoredPost = StoredContent
