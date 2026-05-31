from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


SOURCE_FIELDS = [
    "name",
    "provider",
    "source",
    "url",
    "file",
    "platform",
    "kind",
    "entity",
    "profile",
    "purpose",
    "limit",
    "title",
]


def load_sources(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        return []
    return [dict(item) for item in sources if isinstance(item, dict)]


def save_sources(path: Path, sources: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sources_toml(sources), encoding="utf-8")


def render_sources_toml(sources: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for raw in sources:
        item = normalize_source_item(raw)
        lines = ["[[sources]]"]
        ordered_keys = [key for key in SOURCE_FIELDS if key in item]
        extra_keys = sorted(key for key in item if key not in SOURCE_FIELDS)
        for key in ordered_keys + extra_keys:
            value = item[key]
            if value in (None, ""):
                continue
            lines.append(f"{key} = {toml_value(value)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks).rstrip() + "\n"


def normalize_source_item(raw: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for key, value in raw.items():
        if value in (None, ""):
            continue
        if key == "limit":
            try:
                item[key] = int(value)
            except (TypeError, ValueError):
                continue
        elif isinstance(value, (str, int, float, bool)):
            item[key] = value
    return item


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return quote_toml_string(str(value))


def quote_toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'
