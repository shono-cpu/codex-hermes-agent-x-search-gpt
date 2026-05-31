from __future__ import annotations

from pathlib import Path

from .analysis import build_report
from .render import render_markdown_report
from .store import KnowledgeStore


def export_routed_markdown(
    store: KnowledgeStore,
    out_dir: Path,
    limit: int = 5000,
    clean: bool = False,
    entity: str | None = None,
    profile: str | None = None,
    purpose: str | None = None,
) -> list[Path]:
    if clean and out_dir.exists():
        for path in out_dir.rglob("*.md"):
            path.unlink()

    written: list[Path] = []
    for (group_entity, group_profile, group_purpose, platform), contents in store.route_groups(
        limit=limit,
        entity=entity,
        profile=profile,
        purpose=purpose,
    ).items():
        scope = " / ".join([group_entity, group_profile, group_purpose, platform])
        report = build_report(scope, contents)
        path = out_dir / group_entity / group_profile / group_purpose / f"{platform}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown_report(report), encoding="utf-8")
        written.append(path)
    return sorted(written)
