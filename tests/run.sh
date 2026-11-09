#!/usr/bin/env bash
# Every check this repository has, in order. Stops at the first failure.
#   tests/run.sh
set -euo pipefail
cd "$(dirname "$0")/.."
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
step() { printf '\n== %s\n' "$*" >&2; }

step "leaks"
python3 tests/check_leaks.py

step "every path the documents mention exists"
python3 tests/docs.py

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

fixture="file://$PWD/tests/fixture/grey.html"
ok() { python3 -c 'import json,sys; r=json.loads(sys.stdin.read().strip().splitlines()[-1]); sys.exit(0 if r.get("ok") else (print(r, file=sys.stderr) or 1))'; }

step "two slices side by side, then compare with the single render"
node tools/slices.mjs "$fixture" "$work/sliced" 5 3 0 8 1920 1080 | ok &
node tools/slices.mjs "$fixture" "$work/sliced" 5 3 8 16 1920 1080 | ok &
wait
cmp -s "$work/sliced/f00012.jpg" "$work/frames/f00012.jpg" || { echo "a sliced frame differs from the single render" >&2; exit 1; }

step "render-resume picks up a half-rendered folder"
mkdir -p "$work/resume" && cp "$work/frames/"f0000[0-7].jpg "$work/resume/"
tools/render-resume.sh tests/fixture/grey.html "$work/resume" 3 5 | ok

step "contact sheet and sweep"
node tools/stills.mjs "$fixture" "$work/stills" 0 1 2 3 | ok
[[ -s "$work/stills/sheet.jpg" ]]
node tools/stills.mjs "$fixture" "$work/sweep" --sweep 3 --step 0.25 | ok

step "page tools"
node tools/pagecheck.mjs "$fixture" 'document.querySelectorAll("canvas").length' 20 | ok
node tools/pageshot.mjs "file://$PWD/tests/fixture/grey.html" "$work/page.png" 1200 "" 3 >/dev/null || true
[[ -s "$work/page.png" ]]
node tools/state-probe.mjs "$fixture" 0 1.5 3 | ok

step "the state probe catches a save() that is never restored"
sed 's/^function render(t) {/function render(t) { ctx.save(); ctx.globalAlpha = 0.5;/' tests/fixture/grey.html > "$work/leaky.html"
if node tools/state-probe.mjs "file://$work/leaky.html" 1 >/dev/null 2>&1; then echo "state-probe missed a leak" >&2; exit 1; fi

step "camera samples"
printf '{"format":{"w":1920,"h":1080},"shots":[{"dur":2,"story":[0,1],"camera":[[0,"wide"],[2,{"at":[960,540],"zoom":2}]]}]}' > "$work/shots.json"
node tools/camera.js "$work/shots.json" 1 | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["total"]==2 and r["samples"][-1]["zoom"]==2, r'

step "a film through every step"
tests/spine.sh

step "sound: master, options, sync, narration, Ardour"
tests/sound.sh

step "the demo kit: a real capture drawn in a scene"
tests/demo.sh

step "render lock"
python3 tools/locked.py true

printf '\nall checks passed\n' >&2
