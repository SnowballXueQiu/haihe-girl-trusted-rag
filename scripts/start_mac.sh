#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "缺少 .env。请先执行 cp .env.example .env 并填写模型配置。"
  exit 1
fi

if [[ ! -f .data/index.sqlite ]]; then
  echo "首次运行：正在构建知识索引。"
  uv run python -m backend.scripts.build_index
fi

if [[ ! -d frontend/node_modules ]]; then
  npm --prefix frontend install
fi

npm --prefix frontend run build
app_port=$(uv run python -c 'from backend.app.config import Settings; print(Settings().app_port)')
echo "海河少女已启动：http://127.0.0.1:${app_port}"
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port "$app_port"
