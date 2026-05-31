#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p outputs

STAMP="$(date '+%Y-%m-%dT%H:%M:%S%z')"
LOG="outputs/nakano-monitor.log"

{
  echo "=== nakano-monitor start ${STAMP} ==="
  python3 -m x_knowledge crawl --config sources.toml
  python3 -m x_knowledge export --out-dir knowledge --clean --entity nakano-yusaku
  python3 -m x_knowledge export --out-dir knowledge --entity the-neutral
  python3 -m x_knowledge export --out-dir knowledge --entity buddica
  python3 -m x_knowledge export --out-dir knowledge --entity buddica-phoenix-pro
  echo "=== nakano-monitor end   $(date '+%Y-%m-%dT%H:%M:%S%z') ==="
  echo
} | tee -a "$LOG"

