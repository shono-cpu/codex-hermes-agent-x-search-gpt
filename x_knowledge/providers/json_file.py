from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import ContentInput, PostInput


def load_contents_from_json(
    path: Path,
    source: str | None = None,
    platform: str | None = None,
    kind: str | None = None,
    entity: str | None = None,
    profile: str | None = None,
    purpose: str | None = None,
    min_chars: int = 0,
) -> list[ContentInput]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("JSON input must be a list of content items.")

    contents: list[ContentInput] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each content item must be an object.")
        text = first_string(item, ["text", "content", "description", "transcript", "body", "prompt"])
        if not isinstance(text, str) or not text.strip():
            continue
        if len(text.strip()) < min_chars:
            continue
        item_source = source or first_string(item, ["source", "account", "channel", "author", "creator"])
        if not item_source:
            raise ValueError("Source is required. Pass --source/--account or include source/account/channel.")
        item_platform = first_string(item, ["platform", "media", "medium"]) or platform or "unknown"
        item_kind = first_string(item, ["kind", "type", "asset_type"]) or kind or default_kind(item_platform)
        item_entity = first_string(item, ["entity", "brand", "person", "owner"]) or entity
        item_profile = first_string(item, ["profile", "account_type", "voice"]) or profile or "unknown"
        item_purpose = first_string(item, ["purpose", "use_case", "usage"]) or purpose or "general"
        metadata = merged_metadata(item)
        contents.append(
            ContentInput(
                source=item_source,
                platform=item_platform,
                kind=item_kind,
                entity=item_entity,
                profile=item_profile,
                purpose=item_purpose,
                title=string_or_none(item.get("title")),
                content_id=string_or_none(item.get("id") or item.get("content_id") or item.get("post_id") or item.get("video_id")),
                canonical_key=string_or_none(item.get("canonical_key")),
                url=string_or_none(item.get("url")),
                created_at=string_or_none(item.get("created_at") or item.get("published_at") or item.get("date")),
                text=text.strip(),
                metadata=metadata,
            )
        )
    return contents


def load_posts_from_json(path: Path, account: str) -> list[PostInput]:
    return load_contents_from_json(path, source=account, platform="x", kind="post")


def string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def first_string(item: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = string_or_none(item.get(key))
        if value:
            return value
    return None


def default_kind(platform: str) -> str:
    value = platform.lower()
    if value in {"x", "twitter"}:
        return "post"
    if value == "youtube":
        return "video"
    return "artifact"


def merged_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ["metrics", "metadata"]:
        value = item.get(key)
        if isinstance(value, dict):
            metadata.update(value)
    for key in ["duration", "tags", "language", "format", "status"]:
        if key in item:
            metadata[key] = item[key]
    return metadata
