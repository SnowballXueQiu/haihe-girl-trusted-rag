#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
failed=0

check_file() {
  if [[ -f "$1" ]]; then echo "[OK] $1"; else echo "[缺失] $1"; failed=1; fi
}

check_file "frontend/public/models/haihe-girl.vrm"
check_file ".data/index.sqlite"
check_file "output/pdf/海河少女可信RAG虚拟主播系统设计.pdf"
check_file "paper/main.tex"
check_file "scripts/build_paper.sh"
check_file "output/pdf/海河少女可信RAG虚拟主播系统设计论文.pdf"
check_file "output/pdf/AI工具使用声明.pdf"
check_file "output/pdf/人机协作过程说明.pdf"
check_file "output/pdf/运行与操作说明.pdf"
check_file "output/video/海河少女功能演示.mp4"

if [[ -f paper/main.tex ]]; then
  if rg -q '^\\documentclass' paper/main.tex; then
    echo "[OK] 正式论文 LaTeX 主入口可识别。"
  else
    echo "[失败] paper/main.tex 不含可识别的 \\documentclass。"
    failed=1
  fi
fi
if [[ -f scripts/build_paper.sh && ! -x scripts/build_paper.sh ]]; then
  echo "[失败] scripts/build_paper.sh 不可执行。"
  failed=1
fi
if [[ -f output/pdf/海河少女可信RAG虚拟主播系统设计论文.pdf ]] && \
   find paper -type f \( -name '*.tex' -o -name '*.bib' -o -name '*.sty' \) \
     -newer output/pdf/海河少女可信RAG虚拟主播系统设计论文.pdf -print -quit | rg -q .; then
  echo "[失败] LaTeX 源文件比正式论文 PDF 更新，请重新运行 ./scripts/build_paper.sh。"
  failed=1
fi

if [[ -f frontend/public/models/haihe-girl.vrm ]]; then
  uv run python scripts/validate_vrm.py frontend/public/models/haihe-girl.vrm || failed=1
fi

if compgen -G "submission_materials/报名表.*" >/dev/null; then
  echo "[OK] 学校报名表"
else
  echo "[缺失] submission_materials/报名表.*"
  failed=1
fi
if compgen -G "submission_materials/授权书.*" >/dev/null; then
  echo "[OK] 作品授权书"
else
  echo "[缺失] submission_materials/授权书.*"
  failed=1
fi
if compgen -G "submission_materials/模型授权证明.*" >/dev/null; then
  echo "[OK] VRM 模型授权证明"
else
  echo "[缺失] submission_materials/模型授权证明.*"
  failed=1
fi

if [[ -f .env ]]; then
  generation_provider=$(awk -F= '$1 == "GENERATION_PROVIDER" {print $2; exit}' .env)
  embedding_provider=$(awk -F= '$1 == "EMBEDDING_PROVIDER" {print $2; exit}' .env)
  tts_provider=$(awk -F= '$1 == "TTS_PROVIDER" {print $2; exit}' .env)
  tts_model=$(awk -F= '$1 == "DASHSCOPE_TTS_MODEL" {print $2; exit}' .env)
  tts_voice=$(awk -F= '$1 == "DASHSCOPE_TTS_VOICE" {print $2; exit}' .env)
  tts_language=$(awk -F= '$1 == "DASHSCOPE_TTS_LANGUAGE" {print $2; exit}' .env)
  api_key=$(awk -F= '$1 == "DASHSCOPE_API_KEY" {sub(/^[^=]*=/, ""); print; exit}' .env)
  workspace_id=$(awk -F= '$1 == "DASHSCOPE_WORKSPACE_ID" {sub(/^[^=]*=/, ""); print; exit}' .env)
  if [[ "$generation_provider" != "dashscope" || "$embedding_provider" != "dashscope" ]]; then
    echo "[缺失] 正式演示尚未切换为百炼生成+百炼向量配置。"
    failed=1
  elif [[ -z "$api_key" || -z "$workspace_id" ]]; then
    echo "[缺失] 本机 .env 中的百炼 API Key 或 Workspace ID 尚未配置。"
    failed=1
  else
    echo "[OK] 本机百炼正式配置已填写（密钥不显示）。"
  fi
  if [[ "$tts_provider" != "dashscope" || -z "$tts_model" || -z "$tts_voice" || -z "$tts_language" ]]; then
    echo "[缺失] 百炼语音模型、音色或语言配置不完整。"
    failed=1
  else
    echo "[OK] 百炼语音配置已填写。"
  fi
else
  echo "[缺失] 本机 .env 正式配置。"
  failed=1
fi

if rg -l --hidden \
  --glob '!**/node_modules/**' \
  --glob '!frontend/dist/**' \
  --glob '!.venv/**' \
  --glob '!.env' \
  'DASHSCOPE_API_KEY[[:space:]]*=[[:space:]]*sk-[A-Za-z0-9._-]{16,}|Bearer[[:space:]]+sk-[A-Za-z0-9._-]{16,}' \
  backend frontend/src knowledge docs paper README.md .env.example; then
  echo "[失败] 发现疑似API密钥，请人工检查。"
  failed=1
else
  echo "[OK] 未在提交文件中发现常见密钥格式。"
fi

if [[ -f output/video/海河少女功能演示.mp4 ]]; then
  video_file="output/video/海河少女功能演示.mp4"
  codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$video_file")
  resolution=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$video_file")
  duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$video_file")
  echo "[视频] $codec / $resolution / ${duration}s"
  if [[ "$codec" != "h264" || "$resolution" != "1920x1080" ]]; then
    echo "[失败] 视频必须为 H.264 / 1920x1080。"
    failed=1
  fi
  if ! awk -v value="$duration" 'BEGIN { exit !(value >= 180 && value <= 300) }'; then
    echo "[失败] 视频时长必须在 3–5 分钟。"
    failed=1
  fi
fi

if [[ -f output/pdf/海河少女可信RAG虚拟主播系统设计.pdf ]]; then
  pdfinfo output/pdf/海河少女可信RAG虚拟主播系统设计.pdf | sed -n '1,16p'
fi

total_bytes=$(du -sk backend frontend knowledge docs paper submission_materials output/pdf .data pyproject.toml uv.lock README.md 2>/dev/null | awk '{total += $1} END {print total * 1024}')
if [[ ${total_bytes:-0} -gt 524288000 ]]; then
  echo "[失败] Demo核心文件超过500MB。"
  failed=1
else
  echo "[OK] Demo核心文件约 $(( ${total_bytes:-0} / 1024 / 1024 )) MB。"
fi

exit "$failed"
