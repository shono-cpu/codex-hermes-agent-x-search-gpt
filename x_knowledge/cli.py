from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from .analysis import build_report
from .exporter import export_routed_markdown
from .providers.json_file import load_contents_from_json
from .providers.local_file import load_content_from_file
from .render import render_creative_prompt, render_markdown_report
from .store import DEFAULT_DB, KnowledgeStore, normalize_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nakano-yusaku-bot", description="中野優作bot knowledge workflow helper")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite DB path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize the local knowledge database")

    ingest = sub.add_parser("ingest-json", help="Import content items from a JSON file")
    ingest.add_argument("--source", help="Creator/account/channel/project name")
    ingest.add_argument("--account", help="Backward-compatible alias for --source")
    ingest.add_argument("--platform", help="Platform, e.g. x, youtube, note, website, local")
    ingest.add_argument("--kind", help="Content kind, e.g. post, video, article, slide, image, prompt")
    ingest.add_argument("--min-chars", type=int, default=0, help="Only import items with at least this many characters")
    add_routing_args(ingest)
    ingest.add_argument("--file", type=Path, required=True, help="JSON file containing content items")

    upload = sub.add_parser("ingest-file", help="Import a local text/Markdown file as a content item")
    upload.add_argument("--source", required=True, help="Creator/account/channel/project name")
    upload.add_argument("--platform", default="local", help="Platform, e.g. local, website, youtube")
    upload.add_argument("--kind", default="artifact", help="Content kind, e.g. note, article, prompt, slide")
    upload.add_argument("--title", help="Optional title. Defaults to filename")
    add_routing_args(upload)
    upload.add_argument("--file", type=Path, required=True, help="Text or Markdown file to import")

    report = sub.add_parser("report", help="Create a Markdown knowledge report")
    report.add_argument("--source", help="Creator/account/channel/project name")
    report.add_argument("--account", help="Backward-compatible alias for --source")
    report.add_argument("--platform", help="Optional platform filter")
    add_routing_args(report)
    report.add_argument("--limit", type=int, default=50, help="Number of recent items to analyze")
    report.add_argument("--out", type=Path, help="Output Markdown path")

    prompt = sub.add_parser("prompt", help="Create a creative prompt from stored knowledge")
    prompt.add_argument("--source", help="Creator/account/channel/project name")
    prompt.add_argument("--account", help="Backward-compatible alias for --source")
    prompt.add_argument("--platform", help="Optional platform filter")
    add_routing_args(prompt)
    prompt.add_argument("--goal", required=True, help="Creative goal")
    prompt.add_argument("--asset", default="infographic", help="Asset type, e.g. infographic, article, slide")
    prompt.add_argument("--limit", type=int, default=50, help="Number of recent items to analyze")
    prompt.add_argument("--out", type=Path, help="Output Markdown path")

    export = sub.add_parser("export", help="Export routed Markdown files by entity/profile/purpose/platform")
    export.add_argument("--out-dir", type=Path, default=Path("knowledge"), help="Output directory")
    export.add_argument("--limit", type=int, default=5000, help="Number of recent items to export")
    export.add_argument("--clean", action="store_true", help="Remove old generated Markdown files before exporting")
    add_routing_args(export)

    crawl = sub.add_parser("crawl", help="Run configured crawlers when providers are available")
    crawl.add_argument("--config", type=Path, default=Path("sources.example.toml"), help="Crawler config TOML")

    ui = sub.add_parser("ui", help="Start the local 中野優作bot management UI")
    ui.add_argument("--host", default="127.0.0.1", help="UI host")
    ui.add_argument("--port", type=int, default=8765, help="UI port")
    ui.add_argument("--config", type=Path, default=Path("sources.toml"), help="Crawler config TOML")

    args = parser.parse_args(argv)
    store = KnowledgeStore(args.db)

    if args.command == "init":
        store.init()
        print(f"Initialized {store.db_path}")
        return 0

    if args.command == "ingest-json":
        source = resolve_source(args)
        default_platform = args.platform or ("x" if args.account and not args.source else None)
        contents = load_contents_from_json(
            args.file,
            source=source,
            platform=default_platform,
            kind=args.kind,
            entity=args.entity,
            profile=args.profile,
            purpose=args.purpose,
            min_chars=args.min_chars,
        )
        inserted, updated, skipped = store.upsert_contents(contents)
        print(f"Imported {inserted} items, updated {updated}, skipped {skipped} older duplicates")
        return 0

    if args.command == "ingest-file":
        content = load_content_from_file(
            args.file,
            source=args.source,
            platform=args.platform,
            kind=args.kind,
            entity=args.entity,
            profile=args.profile,
            purpose=args.purpose,
            title=args.title,
        )
        inserted, updated, skipped = store.upsert_contents([content])
        print(f"Imported {inserted} file items, updated {updated}, skipped {skipped} older duplicates")
        return 0

    if args.command == "report":
        source = resolve_source(args, required=False)
        contents = store.recent_contents(
            source=source,
            platform=args.platform,
            entity=args.entity,
            profile=args.profile,
            purpose=args.purpose,
            limit=args.limit,
        )
        report_doc = build_report(report_scope(source, args), contents)
        content = render_markdown_report(report_doc)
        write_or_print(content, args.out)
        return 0

    if args.command == "prompt":
        source = resolve_source(args, required=False)
        contents = store.recent_contents(
            source=source,
            platform=args.platform,
            entity=args.entity,
            profile=args.profile,
            purpose=args.purpose,
            limit=args.limit,
        )
        report_doc = build_report(report_scope(source, args), contents)
        content = render_creative_prompt(report_doc, args.goal, args.asset)
        write_or_print(content, args.out)
        return 0

    if args.command == "export":
        paths = export_routed_markdown(
            store,
            args.out_dir,
            args.limit,
            clean=args.clean,
            entity=args.entity,
            profile=args.profile,
            purpose=args.purpose,
        )
        print(f"Wrote {len(paths)} routed files")
        for path in paths:
            print(path)
        return 0

    if args.command == "crawl":
        return crawl_from_config(args.config, store)

    if args.command == "ui":
        from .ui_server import run_ui

        run_ui(host=args.host, port=args.port, config=args.config, db=args.db)
        return 0

    parser.error("Unknown command")
    return 2


def write_or_print(content: str, out: Path | None) -> None:
    if out is None:
        print(content)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"Wrote {out}")


def add_routing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--entity", help="Person/company/brand this item belongs to")
    parser.add_argument("--profile", help="personal or company")
    parser.add_argument("--purpose", help="Usage bucket, e.g. style, research, creative, sales")


def resolve_source(args: argparse.Namespace, required: bool = True) -> str | None:
    source = args.source or args.account
    if required and not source:
        raise SystemExit("--source is required. Use --account for old X-only commands.")
    if source is None:
        return None
    platform = getattr(args, "platform", "") or ("x" if args.account and not args.source else "")
    return normalize_source(source, platform)


def report_scope(source: str | None, args: argparse.Namespace) -> str:
    parts = []
    if args.entity:
        parts.append(args.entity)
    if args.profile:
        parts.append(args.profile)
    if args.purpose:
        parts.append(args.purpose)
    platform = getattr(args, "platform", None)
    if source and platform:
        parts.append(f"{source} on {platform}")
    elif source:
        parts.append(source)
    elif platform:
        parts.append(f"all sources on {platform}")
    return " / ".join(parts) if parts else "all sources"


def crawl_from_config(config_path: Path, store: KnowledgeStore) -> int:
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        raise SystemExit("Config must contain [[sources]] entries.")

    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    unavailable: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        provider = str(source.get("provider", "")).strip().lower()
        if provider == "json":
            file_path = Path(str(source["file"]))
            contents = load_contents_from_json(
                file_path,
                source=str(source.get("source") or source.get("name") or ""),
                platform=optional_str(source.get("platform")),
                kind=optional_str(source.get("kind")),
                entity=optional_str(source.get("entity")),
                profile=optional_str(source.get("profile")),
                purpose=optional_str(source.get("purpose")),
                min_chars=int(source.get("min_chars") or 0),
            )
            inserted, updated, skipped = store.upsert_contents(contents)
            total_inserted += inserted
            total_updated += updated
            total_skipped += skipped
        elif provider == "local_file":
            file_path = Path(str(source["file"]))
            content = load_content_from_file(
                file_path,
                source=str(source.get("source") or source.get("name") or file_path.stem),
                platform=optional_str(source.get("platform")) or "local",
                kind=optional_str(source.get("kind")) or "artifact",
                entity=optional_str(source.get("entity")),
                profile=optional_str(source.get("profile")),
                purpose=optional_str(source.get("purpose")),
                title=optional_str(source.get("title")),
            )
            inserted, updated, skipped = store.upsert_contents([content])
            total_inserted += inserted
            total_updated += updated
            total_skipped += skipped
        else:
            detail = f"{source.get('name') or source.get('source')} ({provider or 'no provider'})"
            if source.get("min_chars"):
                detail += f", min_chars={source.get('min_chars')}"
            unavailable.append(detail)

    print(f"Crawl imported {total_inserted}, updated {total_updated}, skipped {total_skipped}")
    if unavailable:
        print("Providers not implemented in this local session:")
        for item in unavailable:
            print(f"- {item}")
    return 0


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


if __name__ == "__main__":
    raise SystemExit(main())
