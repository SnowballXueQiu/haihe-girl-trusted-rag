#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
paper_dir="$project_dir/paper"
build_dir="$paper_dir/build"
pdf_dir="$project_dir/output/pdf"
paper_pdf="$pdf_dir/海河少女可信RAG虚拟主播系统设计论文.pdf"
stable_pdf="$pdf_dir/海河少女可信RAG虚拟主播系统设计.pdf"

for command_name in latexmk xelatex biber; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "[缺失] $command_name；请安装包含 XeLaTeX 与 biber 的 TeX Live。" >&2
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
    main.tex
)

cp -f "$build_dir/main.pdf" "$paper_pdf"
cp -f "$paper_pdf" "$stable_pdf"

if command -v pdfinfo >/dev/null 2>&1; then
  pdfinfo "$paper_pdf" | grep -E 'Pages:|Page size:|PDF version:'
fi

if command -v gs >/dev/null 2>&1; then
  gs -q -dNOPAUSE -dBATCH -sDEVICE=nullpage "$paper_pdf"
  echo "[OK] Ghostscript 已完整解析论文 PDF。"
fi

echo "[OK] $paper_pdf"
echo "[OK] $stable_pdf"
