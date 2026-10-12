#!/usr/bin/env bash
# Run from the repository root after sourcing source_me.sh.
set -euo pipefail

capture_dir="$(mktemp -d /tmp/book_markdown_capture.XXXXXX)"
trap 'rm -rf "$capture_dir"' EXIT
python3 devel/readme_demo.py > "$capture_dir/transcript.txt"
magick -background '#101820' -fill '#e6edf3' \
	-font /System/Library/Fonts/Menlo.ttc -pointsize 18 \
	"label:@$capture_dir/transcript.txt" -bordercolor '#101820' -border 36 \
	-gravity center -extent 1280x800 "$capture_dir/cleanup_demo.png"
mkdir -p docs/screenshots
cp "$capture_dir/cleanup_demo.png" docs/screenshots/cleanup_demo.png
printf 'Captured docs/screenshots/cleanup_demo.png\n'
