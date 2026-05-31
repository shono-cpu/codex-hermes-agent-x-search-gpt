from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ContentInput, StoredContent, PostInput, StoredPost


DEFAULT_DB = Path("data/knowledge.sqlite")


SCHEMA = """
CREATE TABLE IF NOT EXISTS contents (
  content_id TEXT PRIMARY KEY,
  canonical_key TEXT UNIQUE,
  platform TEXT NOT NULL,
  source TEXT NOT NULL,
  kind TEXT NOT NULL,
  entity TEXT,
  profile TEXT NOT NULL DEFAULT 'unknown',
  purpose TEXT NOT NULL DEFAULT 'general',
  title TEXT,
  text TEXT NOT NULL,
  url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contents_source_created
ON contents(source, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contents_platform_source_created
ON contents(platform, source, created_at DESC);

CREATE TABLE IF NOT EXISTS posts (
  post_id TEXT PRIMARY KEY,
  account TEXT NOT NULL,
  text TEXT NOT NULL,
  url TEXT,
  created_at TEXT NOT NULL,
  metrics_json TEXT NOT NULL DEFAULT '{}',
  inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_posts_account_created
ON posts(account, created_at DESC);

CREATE TABLE IF NOT EXISTS sync_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class KnowledgeStore:
    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            migrate_contents_schema(conn)
            migrate_legacy_posts(conn)

    def get_state(self, key: str) -> str | None:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_state(self, key: str, value: str) -> None:
        self.init()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_state(key, value, updated_at)
                VALUES(?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def upsert_contents(self, contents: list[ContentInput]) -> tuple[int, int, int]:
        self.init()
        inserted = 0
        updated = 0
        skipped = 0
        with self.connect() as conn:
            for content in contents:
                canonical_key = content.normalized_canonical_key()
                created_at = content.normalized_created_at()
                existing = conn.execute(
                    """
                    SELECT content_id, created_at, updated_at
                    FROM contents
                    WHERE canonical_key = ?
                    """,
                    (canonical_key,),
                ).fetchone()
                if existing is not None:
                    if is_newer_or_same(created_at, existing["created_at"]):
                        conn.execute(
                            """
                            UPDATE contents
                            SET content_id = ?,
                                platform = ?,
                                source = ?,
                                kind = ?,
                                entity = ?,
                                profile = ?,
                                purpose = ?,
                                title = ?,
                                text = ?,
                                url = ?,
                                created_at = ?,
                                updated_at = CURRENT_TIMESTAMP,
                                metadata_json = ?
                            WHERE canonical_key = ?
                            """,
                            update_values(content, created_at) + (canonical_key,),
                        )
                        updated += 1
                    else:
                        skipped += 1
                    continue

                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO contents(
                      content_id, canonical_key, platform, source, kind, entity, profile, purpose,
                      title, text, url, created_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    content_values(content, canonical_key, created_at),
                )
                if cursor.rowcount:
                    inserted += 1
                else:
                    skipped += 1
        return inserted, updated, skipped

    def upsert_posts(self, posts: list[PostInput]) -> tuple[int, int, int]:
        return self.upsert_contents(posts)

    def recent_contents(
        self,
        source: str | None = None,
        limit: int = 50,
        platform: str | None = None,
        entity: str | None = None,
        profile: str | None = None,
        purpose: str | None = None,
    ) -> list[StoredContent]:
        self.init()
        clauses: list[str] = []
        params: list[object] = []
        if source:
            clauses.append("source = ?")
            params.append(normalize_source(source, platform or ""))
        if platform:
            clauses.append("platform = ?")
            params.append(normalize_platform(platform))
        if entity:
            clauses.append("entity = ?")
            params.append(normalize_entity(entity))
        if profile:
            clauses.append("profile = ?")
            params.append(normalize_profile(profile))
        if purpose:
            clauses.append("purpose = ?")
            params.append(normalize_purpose(purpose))

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT content_id, canonical_key, platform, source, kind, entity, profile, purpose,
                       title, text, url, created_at, updated_at, metadata_json
                FROM contents
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [
            StoredContent(
                content_id=row["content_id"],
                canonical_key=row["canonical_key"],
                platform=row["platform"],
                source=row["source"],
                kind=row["kind"],
                entity=row["entity"],
                profile=row["profile"],
                purpose=row["purpose"],
                title=row["title"],
                text=row["text"],
                url=row["url"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata_json=row["metadata_json"],
            )
            for row in rows
        ]

    def route_groups(
        self,
        limit: int = 5000,
        entity: str | None = None,
        profile: str | None = None,
        purpose: str | None = None,
    ) -> dict[tuple[str, str, str, str], list[StoredContent]]:
        contents = self.recent_contents(limit=limit, entity=entity, profile=profile, purpose=purpose)
        groups: dict[tuple[str, str, str, str], list[StoredContent]] = {}
        for content in contents:
            key = (
                slug(content.entity or "unknown"),
                slug(content.profile),
                slug(content.purpose),
                slug(content.platform),
            )
            groups.setdefault(key, []).append(content)
        return groups

    def recent_posts(self, account: str, limit: int = 50) -> list[StoredPost]:
        return self.recent_contents(source=account, limit=limit, platform="x")


def normalize_account(account: str) -> str:
    return normalize_source(account, "x")


def normalize_source(source: str, platform: str = "") -> str:
    value = source.strip()
    if normalize_platform(platform) in {"x", "twitter"} and value and not value.startswith("@"):
        return f"@{value}"
    return value


def normalize_platform(platform: str) -> str:
    value = platform.strip().lower()
    if value in {"twitter", "tweet"}:
        return "x"
    if value in {"yt"}:
        return "youtube"
    return value or "unknown"


def normalize_profile(profile: str | None) -> str:
    value = (profile or "unknown").strip().lower()
    aliases = {
        "personal": "personal",
        "person": "personal",
        "individual": "personal",
        "個人": "personal",
        "company": "company",
        "corp": "company",
        "corporate": "company",
        "official": "company",
        "公式": "company",
        "会社": "company",
    }
    return aliases.get(value, value or "unknown")


def normalize_purpose(purpose: str | None) -> str:
    return slug(purpose or "general")


def normalize_entity(entity: str | None) -> str | None:
    value = (entity or "").strip()
    return value or None


def slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "unknown"


def content_values(content: ContentInput, canonical_key: str, created_at: str) -> tuple[object, ...]:
    platform = normalize_platform(content.platform)
    return (
        content.normalized_id(),
        canonical_key,
        platform,
        normalize_source(content.source, platform),
        content.kind.strip().lower() or "item",
        normalize_entity(content.entity),
        normalize_profile(content.profile),
        normalize_purpose(content.purpose),
        content.title,
        content.text,
        content.url,
        created_at,
        json.dumps(content.metadata, ensure_ascii=False, sort_keys=True),
    )


def update_values(content: ContentInput, created_at: str) -> tuple[object, ...]:
    platform = normalize_platform(content.platform)
    return (
        content.normalized_id(),
        platform,
        normalize_source(content.source, platform),
        content.kind.strip().lower() or "item",
        normalize_entity(content.entity),
        normalize_profile(content.profile),
        normalize_purpose(content.purpose),
        content.title,
        content.text,
        content.url,
        created_at,
        json.dumps(content.metadata, ensure_ascii=False, sort_keys=True),
    )


def is_newer_or_same(incoming: str, existing: str) -> bool:
    return incoming >= existing


def migrate_contents_schema(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(contents)").fetchall()
    }
    additions = {
        "canonical_key": "ALTER TABLE contents ADD COLUMN canonical_key TEXT",
        "entity": "ALTER TABLE contents ADD COLUMN entity TEXT",
        "profile": "ALTER TABLE contents ADD COLUMN profile TEXT NOT NULL DEFAULT 'unknown'",
        "purpose": "ALTER TABLE contents ADD COLUMN purpose TEXT NOT NULL DEFAULT 'general'",
        "updated_at": "ALTER TABLE contents ADD COLUMN updated_at TEXT",
    }
    for column, statement in additions.items():
        if column not in columns:
            conn.execute(statement)

    rows = conn.execute(
        """
        SELECT content_id, platform, source, kind, title, text, url
        FROM contents
        WHERE canonical_key IS NULL OR canonical_key = ''
        """
    ).fetchall()
    for row in rows:
        if row["url"]:
            seed = f"{row['platform']}|url|{row['url']}"
        elif row["title"]:
            seed = f"{row['platform']}|title|{row['source']}|{row['title']}"
        else:
            seed = f"{row['platform']}|id|{row['content_id']}"
        conn.execute(
            "UPDATE contents SET canonical_key = ? WHERE content_id = ?",
            (json_hash(seed), row["content_id"]),
        )
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_contents_canonical_key ON contents(canonical_key)")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_contents_route
        ON contents(entity, profile, purpose, platform, kind)
        """
    )


def migrate_legacy_posts(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'posts'"
    ).fetchone()
    if table is None:
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO contents(
          content_id, canonical_key, platform, source, kind, entity, profile, purpose,
          title, text, url, created_at, metadata_json, inserted_at
        )
        SELECT post_id,
               lower(hex(randomblob(16))),
               'x',
               account,
               'post',
               NULL,
               'unknown',
               'general',
               NULL,
               text,
               url,
               created_at,
               metrics_json,
               inserted_at
        FROM posts
        """
    )


def json_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
