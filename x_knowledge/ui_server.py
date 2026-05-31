from __future__ import annotations

import contextlib
import io
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .cli import crawl_from_config
from .exporter import export_routed_markdown
from .llm import settings_status
from .providers.local_file import load_content_from_file
from .refine import refine_for_nakano, save_artifact
from .source_config import load_sources, save_sources
from .store import DEFAULT_DB, KnowledgeStore


ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"


class BotUIHandler(BaseHTTPRequestHandler):
    server_version = "NakanoYusakuBotUI/0.1"

    @property
    def config_path(self) -> Path:
        return self.server.config_path  # type: ignore[attr-defined]

    @property
    def store(self) -> KnowledgeStore:
        return self.server.store  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/sources":
            return self.send_json({"sources": load_sources(self.config_path), "config": str(self.config_path)})
        if parsed.path == "/api/status":
            return self.send_json({"ok": True, "config": str(self.config_path), "db": str(self.store.db_path), "llm": settings_status()})
        return self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/sources":
            body = self.read_json()
            sources = body.get("sources")
            if not isinstance(sources, list):
                return self.send_json({"error": "sources must be a list"}, HTTPStatus.BAD_REQUEST)
            save_sources(self.config_path, [item for item in sources if isinstance(item, dict)])
            return self.send_json({"ok": True, "sources": load_sources(self.config_path)})

        if parsed.path == "/api/crawl":
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = crawl_from_config(self.config_path, self.store)
            return self.send_json({"ok": code == 0, "output": output.getvalue()})

        if parsed.path == "/api/export":
            body = self.read_json(default={})
            paths = export_routed_markdown(
                self.store,
                Path(str(body.get("out_dir") or "knowledge")),
                int(body.get("limit") or 5000),
                clean=bool(body.get("clean", True)),
                entity=optional_str(body.get("entity")),
                profile=optional_str(body.get("profile")),
                purpose=optional_str(body.get("purpose")),
            )
            return self.send_json({"ok": True, "paths": [str(path) for path in paths]})

        if parsed.path == "/api/ingest-file":
            body = self.read_json()
            try:
                content = load_content_from_file(
                    Path(str(body["file"])),
                    source=str(body.get("source") or "Manual Upload"),
                    platform=str(body.get("platform") or "local"),
                    kind=str(body.get("kind") or "artifact"),
                    entity=optional_str(body.get("entity")),
                    profile=optional_str(body.get("profile")),
                    purpose=optional_str(body.get("purpose")),
                    title=optional_str(body.get("title")),
                )
                inserted, updated, skipped = self.store.upsert_contents([content])
            except Exception as exc:  # noqa: BLE001 - API should return readable local errors.
                return self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return self.send_json({"ok": True, "inserted": inserted, "updated": updated, "skipped": skipped})

        if parsed.path == "/api/artifact":
            body = self.read_json()
            text = str(body.get("text") or "").strip()
            if not text:
                return self.send_json({"ok": False, "error": "text is required"}, HTTPStatus.BAD_REQUEST)
            inserted, updated, skipped = save_artifact(
                self.store,
                title=str(body.get("title") or "制作物"),
                text=text,
                entity=str(body.get("entity") or "nakano-yusaku"),
                profile=str(body.get("profile") or "personal"),
                purpose=str(body.get("purpose") or "creative"),
                kind=str(body.get("kind") or "draft"),
                source=str(body.get("source") or "中野優作bot UI"),
            )
            return self.send_json({"ok": True, "inserted": inserted, "updated": updated, "skipped": skipped})

        if parsed.path == "/api/chat/refine":
            body = self.read_json()
            result = refine_for_nakano(
                self.store,
                draft=str(body.get("draft") or ""),
                instruction=str(body.get("message") or ""),
                entity=str(body.get("entity") or "nakano-yusaku"),
                profile=str(body.get("profile") or "personal"),
                purpose=str(body.get("style_purpose") or "style"),
                asset=str(body.get("asset") or "post"),
            )
            return self.send_json({"ok": True, **result})

        return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def serve_static(self, path: str) -> None:
        route = "index.html" if path in {"", "/"} else path.lstrip("/")
        file_path = (UI_DIR / route).resolve()
        if UI_DIR.resolve() not in file_path.parents and file_path != UI_DIR.resolve():
            return self.send_json({"error": "invalid path"}, HTTPStatus.BAD_REQUEST)
        if not file_path.exists() or not file_path.is_file():
            file_path = UI_DIR / "index.html"
        content_type = "text/html; charset=utf-8"
        if file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self, default: dict[str, object] | None = None) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return default or {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_ui(host: str = "127.0.0.1", port: int = 8765, config: Path = Path("sources.toml"), db: Path = DEFAULT_DB) -> None:
    server = ThreadingHTTPServer((host, port), BotUIHandler)
    server.config_path = config
    server.store = KnowledgeStore(db)
    print(f"中野優作bot UI: http://{host}:{port}")
    print(f"Config: {config}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping UI")
    finally:
        server.server_close()


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
