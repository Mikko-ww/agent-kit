#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REGISTRY_PATH="$REPO_ROOT/registry/official.json"
readonly BUMP_TYPES=("patch" "minor" "major")
AVAILABLE_PLUGINS=""


load_plugins() {
  AVAILABLE_PLUGINS="$(
    python3 - "$REGISTRY_PATH" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for plugin_id in sorted((payload.get("plugins") or {}).keys()):
    print(plugin_id)
PY
  )"
}


print_plugins() {
  local plugin_id
  while IFS= read -r plugin_id; do
    if [[ -n "$plugin_id" ]]; then
      echo "  - $plugin_id"
    fi
  done <<< "$AVAILABLE_PLUGINS"
}


print_usage() {
  local output="${1:-stderr}"
  local fd=2
  if [[ "$output" == "stdout" ]]; then
    fd=1
  fi

  {
    echo "用法: ./scripts/release/ak-release.sh <plugin-id> <patch|minor|major>"
    echo "可用插件:"
    print_plugins
    echo "可用版本类型: ${BUMP_TYPES[*]}"
  } >&"$fd"
}


plugin_exists() {
  local target="$1"
  local plugin_id
  while IFS= read -r plugin_id; do
    if [[ "$plugin_id" == "$target" ]]; then
      return 0
    fi
  done <<< "$AVAILABLE_PLUGINS"
  return 1
}


bump_is_valid() {
  local target="$1"
  local bump
  for bump in "${BUMP_TYPES[@]}"; do
    if [[ "$bump" == "$target" ]]; then
      return 0
    fi
  done
  return 1
}


load_plugins

if [[ $# -eq 1 ]] && [[ "$1" == "--help" || "$1" == "-h" ]]; then
  print_usage stdout
  exit 0
fi

if [[ $# -eq 0 ]]; then
  echo "缺少参数。" >&2
  print_usage stderr
  exit 1
fi

plugin_id="$1"
if ! plugin_exists "$plugin_id"; then
  echo "插件无效: $plugin_id" >&2
  print_usage stderr
  exit 1
fi

if [[ $# -eq 1 ]]; then
  echo "还需要提供版本类型: patch|minor|major" >&2
  print_usage stderr
  exit 1
fi

version_bump="$2"
if ! bump_is_valid "$version_bump"; then
  echo "版本类型无效: $version_bump" >&2
  print_usage stderr
  exit 1
fi

if [[ $# -ne 2 ]]; then
  echo "参数数量不正确。" >&2
  print_usage stderr
  exit 1
fi

cd "$REPO_ROOT"
exec uv run python scripts/release/release_plugin.py "$plugin_id" "$version_bump"
