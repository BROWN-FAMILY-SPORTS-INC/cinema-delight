#!/usr/bin/env bash
# Every check this repository has, in order. Stops at the first failure.
#   tests/run.sh
set -euo pipefail
cd "$(dirname "$0")/.."
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
step() { printf '\n== %s\n' "$*" >&2; }

step "leaks"
python3 tests/check_leaks.py

step "render the fixture: 3 s at 5 fps"
node tools/render.mjs "file://$PWD/tests/fixture/grey.html" "$work/frames" 5 3 0 1920 1080
frames=$(ls "$work/frames" | wc -l)
[[ "$frames" == 16 ]] || { echo "expected 16 frames, got $frames" >&2; exit 1; }

step "encode and measure"
ffmpeg -hide_banner -loglevel error -y -framerate 5 -i "$work/frames/f%05d.jpg" -c:v libx264 -pix_fmt yuv420p "$work/fixture.mp4"
IFS=, read -r w h n < <(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=width,height,nb_read_frames -of csv=p=0 "$work/fixture.mp4")
[[ "$w x $h x $n" == "1920 x 1080 x 16" ]] || { echo "expected 1920 x 1080 x 16, got $w x $h x $n" >&2; exit 1; }

step "one still"
tools/still.sh "file://$PWD/tests/fixture/grey.html" 1.5 "$work/still.png" >/dev/null

printf '\nall checks passed\n' >&2
