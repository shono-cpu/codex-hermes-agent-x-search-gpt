#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p outputs

STAMP="$(date '+%Y-%m-%dT%H:%M:%S%z')"
LOG="outputs/nakano-monitor.log"
TMP_RUN_OUT="$(mktemp)"

{
  echo "=== nakano-monitor start ${STAMP} ==="
  DB_PATH="${THE_NEUTRAL_AGENTS_DB_PATH:-data/the-neutral-agents.sqlite}"
  if [[ ! -f "$DB_PATH" ]]; then
    python3 -m x_knowledge --db "$DB_PATH" init
  fi

  if [[ -n "${LINE_WORKER_ENDPOINT:-}" ]]; then
    if [[ -n "${LINE_EXPORT_TOKEN:-}" ]]; then
      python3 -m x_knowledge --db "$DB_PATH" line-sync --endpoint "$LINE_WORKER_ENDPOINT" --token "$LINE_EXPORT_TOKEN" || true
    else
      python3 -m x_knowledge --db "$DB_PATH" line-sync --endpoint "$LINE_WORKER_ENDPOINT" || true
    fi
  fi

  python3 -m x_knowledge --db "$DB_PATH" crawl --config sources.toml
  python3 -m x_knowledge --db "$DB_PATH" export --out-dir knowledge --clean --entity nakano-yusaku
  python3 -m x_knowledge --db "$DB_PATH" export --out-dir knowledge --entity the-neutral
  python3 -m x_knowledge --db "$DB_PATH" export --out-dir knowledge --entity buddica
  python3 -m x_knowledge --db "$DB_PATH" export --out-dir knowledge --entity buddica-phoenix-pro
  echo "=== nakano-monitor end   $(date '+%Y-%m-%dT%H:%M:%S%z') ==="
  echo
} | tee -a "$LOG" | tee "$TMP_RUN_OUT"

if [[ -n "${LINE_NOTIFY_TO:-}" && -n "${LINE_CHANNEL_ACCESS_TOKEN:-}" ]]; then
  MSG="$(tail -n 40 "$TMP_RUN_OUT")"
  python3 -m x_knowledge notify-line --to "$LINE_NOTIFY_TO" --access-token "$LINE_CHANNEL_ACCESS_TOKEN" --message "$MSG" || true
fi

rm -f "$TMP_RUN_OUT"
