#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
paper_dir="$project_dir/paper"
build_dir="$paper_dir/build/ai-tools-statement"
pdf_dir="$project_dir/output/pdf"
output_pdf="$pdf_dir/AI工具使用声明.pdf"

for command_name in latexmk xelatex; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "[缺失] $command_name；请安装包含 XeLaTeX 的 TeX Live。" >&2
    exit 1
  fi
done

mkdir -p "$build_dir" "$pdf_dir"

(
  cd "$paper_dir"
  latexmk \
    -xelatex \
    -interaction=nonstopmode \
    -halt-on-error \
    -file-line-error \
    -outdir="$build_dir" \
    ai_tools_statement.tex
)

cp -f "$build_dir/ai_tools_statement.pdf" "$output_pdf"

if command -v pdfinfo >/dev/null 2>&1; then
  pdfinfo "$output_pdf" | grep -E 'Pages:|Page size:|PDF version:'
fi

if command -v gs >/dev/null 2>&1; then
  gs -q -dNOPAUSE -dBATCH -sDEVICE=nullpage "$output_pdf"
  echo "[OK] Ghostscript 已完整解析 PDF。"
fi

echo "[OK] $output_pdf"
