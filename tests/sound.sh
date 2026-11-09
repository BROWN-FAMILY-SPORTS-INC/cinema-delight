#!/usr/bin/env bash
# The sound tools on generated audio: mastering, the options page and pick, the Ardour cleanup of a
# voice and music (skipped, and said so, when Ardour is not installed), and the sync check catching
# a sound 300 ms early and passing it once moved.
set -eu   # no pipefail: results are judged by has/expect
cd "$(dirname "$0")/.."
name="sound-test-$$"
d="films/$name"
w="$(mktemp -d)"
trap 'rm -rf "$d" ".frames/$name" "$w"' EXIT
j() { python3 -c 'import json,sys; r=json.loads(sys.stdin.read().strip().splitlines()[-1]); print(r'"$1"')'; }
has() { local o; o=$(cat); [[ "$o" == *"$1"* ]] || { echo "expected to find: $1 in: $o" >&2; exit 1; }; }

echo "master: a tone reaches -16 LUFS under a -1 dBTP ceiling" >&2
ffmpeg -v error -y -f lavfi -i "sine=f=330:d=8" -af volume=-20dB -ac 2 "$w/quiet.wav"
python3 tools/master.py "$w/quiet.wav" "$w/mastered.wav" | python3 -c '
import json,sys; r=json.loads(sys.stdin.read().strip().splitlines()[-1]); a=r["after"]
assert r["ok"] and abs(a["integrated_lufs"] + 16) < 0.6 and a["true_peak_dbtp"] <= -0.9, r'

python3 tools/film.py new "$name" "Sound test." >/dev/null
printf '{"format": "beats/1", "parts": [{"id": "only", "dur": 3, "beats": [{"id": "pop", "t": 1.5, "kind": "action", "sound": "hit", "what": "a white square appears"}]}]}\n' > "$d/beats.json"
sed 's/^function render(t) {/function render(t) { ctx.globalAlpha = 1;/; s/^  ctx.fillText(`t = ${t.toFixed(2)} s`, W \/ 2, 520);/  if (t >= 1.5) { ctx.fillStyle = "#fff"; ctx.fillRect(760, 340, 400, 400); }/' tests/fixture/grey.html > "$d/scene/scene.html"
grep -q 'fillRect(760' "$d/scene/scene.html"

echo "options page and pick" >&2
for at in 1.2 1.5; do
  ffmpeg -v error -y -f lavfi -i "aevalsrc='if(between(t,$at,$at+0.03),0.8*sin(2*PI*1000*t),0)':d=3.5:s=48000" -ac 2 "$d/song/options/click-$at.wav"
done
python3 tools/options.py "$name" page | j '["options"]' | has "click-1.2.wav"
python3 tools/options.py "$name" pick options/click-1.2.wav --said "the early one, for the test" | j '["ok"]' | has True

echo "sync calls a click 300 ms before its picture early" >&2
python3 tools/film.py draft "$name" --fps 30 --jobs 2 | j '["ok"]' | has True
python3 tools/sync.py "$name" | j '["cues"][0]["verdict"]' | has early
python3 tools/options.py "$name" pick options/click-1.5.wav --said "the moved one" >/dev/null
python3 tools/film.py draft "$name" --fps 30 --jobs 2 >/dev/null
python3 tools/sync.py "$name" --write-visible | j '["ok"]' | has True
python3 -c "import json; b=json.load(open('$d/beats.json')); assert b['measured'] and abs(b['parts'][0]['beats'][0]['visible'] - 1.5) < 0.05, b"

ffmpeg -v error -y -f lavfi -i "sine=f=200:d=3" -ac 2 "$w/voice.wav"
ffmpeg -v error -y -f lavfi -i "anoisesrc=d=3:a=0.2" -ac 2 "$w/music.wav"

if command -v ardour9-lua >/dev/null && command -v ardour9-export >/dev/null; then
  echo "Ardour cleanup: a session and a bounce of the right length" >&2
  printf '{"rate": 48000, "seconds": 3, "parts": [{"name": "voice", "file": "voice.wav"}, {"name": "music", "file": "music.wav", "gain_db": -6}]}' > "$w/stems.json"
  printf '{"inserts": [{"tracks": "voice", "plugin": "eq_7band", "params": {"hpf_on": 1, "hpf_freq": 80}}, {"tracks": "voice", "plugin": "compressor", "params": {"ratio": 3}}]}' > "$w/desk.json"
  python3 tools/ardour.py "$w/stems.json" --session "$w/session" --bounce "$w/clean.wav" --desk "$w/desk.json" | j '["ok"]' | has True
  [[ "$(ffprobe -v error -show_entries stream=duration -of csv=p=0 "$w/clean.wav")" == 3.0* ]]
else
  echo "SKIPPED: Ardour cleanup (ardour9-lua and ardour9-export are not installed)" >&2
fi
echo "sound: every check passed" >&2
