$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".env")) {
  Write-Error "缺少 .env。请先复制 .env.example 为 .env 并填写模型配置。"
}

if (-not (Test-Path ".data/index.sqlite")) {
  Write-Host "首次运行：正在构建知识索引。"
  uv run python -m backend.scripts.build_index
}

if (-not (Test-Path "frontend/node_modules")) {
  npm --prefix frontend install
}

npm --prefix frontend run build
$AppPort = (uv run python -c "from backend.app.config import Settings; print(Settings().app_port)").Trim()
Write-Host "海河少女已启动：http://127.0.0.1:$AppPort"
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port $AppPort
