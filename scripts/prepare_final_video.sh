#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <原始录屏文件>"
  echo "示例：$0 ~/Desktop/haihe-demo.mov"
  exit 2
fi

source_video="$1"
target_video="output/video/海河少女功能演示.mp4"
if [[ ! -f "$source_video" ]]; then
  echo "原始视频不存在：$source_video"
  exit 1
fi

mkdir -p output/video
ffmpeg -hide_banner -y -i "$source_video" \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -movflags +faststart \
  "$target_video"

duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$target_video")"
codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$target_video")"
resolution="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$target_video")"
echo "已输出：$target_video"
echo "视频：$codec / $resolution / ${duration}s"
