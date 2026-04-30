#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "请使用 source scripts/dev/dev-env.sh 载入当前终端环境" >&2
  exit 1
fi

export AGENT_KIT_CONFIG_DIR="$PWD/.tmp/config"
export AGENT_KIT_DATA_DIR="$PWD/.tmp/data"
export AGENT_KIT_CACHE_DIR="$PWD/.tmp/cache"

mkdir -p "$AGENT_KIT_CONFIG_DIR" "$AGENT_KIT_DATA_DIR" "$AGENT_KIT_CACHE_DIR"

ak() {
  if [[ $# -gt 0 ]]; then
    case "$1" in
      skills-link|opencode-env-switch|planning-files-skill)
        local plugin_id="$1"
        shift
        uv run python scripts/dev/run_workspace_plugin.py "$plugin_id" "$@"
        return $?
        ;;
    esac
  fi

  uv run agent-kit "$@"
}

echo "已设置 AGENT_KIT_CONFIG_DIR=$AGENT_KIT_CONFIG_DIR"
echo "已设置 AGENT_KIT_DATA_DIR=$AGENT_KIT_DATA_DIR"
echo "已设置 AGENT_KIT_CACHE_DIR=$AGENT_KIT_CACHE_DIR"
echo "已启用命令 ak"
