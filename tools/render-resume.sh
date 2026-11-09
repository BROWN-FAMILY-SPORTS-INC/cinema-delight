#!/usr/bin/env bash
# Render a scene to frames, relaunching the browser until every frame is on disk.
#
#   tools/render-resume.sh <scene.html> <frames-dir> [seconds=10] [fps=60] [w=1920] [h=1080] [tries=40]
#
# tools/render.mjs skips frames already on disk, so each relaunch resumes where the last one stopped.
# On a busy machine a long-lived headless browser can be killed for memory partway through a long
# render; this keeps going. A zero-byte frame (a write cut off by a kill) is deleted before each
# attempt, so it is drawn again rather than encoded black.
set -u
cd "$(dirname "$0")/.."
SCENE=$(realpath "$1"); OUT=$2; SECS=${3:-10}; FPS=${4:-60}; W=${5:-1920}; H=${6:-1080}; TRIES=${7:-40}
TARGET=$(python3 -c "print(round($SECS * $FPS) + 1)")   # frames 0 .. secs*fps inclusive, as render.mjs writes them
mkdir -p "$OUT"
i=0
while :; do
  find "$OUT" -maxdepth 1 -name 'f*.jpg' -size 0 -delete
  have=$(find "$OUT" -maxdepth 1 -name 'f*.jpg' | wc -l)
  [ "$have" -ge "$TARGET" ] && break
  if [ "$i" -ge "$TRIES" ]; then
    printf '{"ok": false, "wrote": ["%s"], "problems": ["gave up after %s attempts at %s of %s frames"]}\n' "$OUT" "$i" "$have" "$TARGET"
    exit 1
  fi
  i=$((i + 1))
  echo "attempt $i: $have/$TARGET frames on disk" >&2
  node tools/render.mjs "file://$SCENE" "$OUT" "$FPS" "$SECS" 0 "$W" "$H" >/dev/null
  sleep 2
done
printf '{"ok": true, "wrote": ["%s"], "frames": %s, "attempts": %s, "problems": []}\n' "$OUT" "$TARGET" "$i"
