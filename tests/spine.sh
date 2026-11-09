#!/usr/bin/env bash
# One tiny film through every step of the build order, start to finish, then removed.
set -eu   # no pipefail: each result is judged by has/expect, and a tool that reports a problem exits 1 on purpose
cd "$(dirname "$0")/.."
name="spine-test-$$"
d="films/$name"
trap 'rm -rf "$d" ".frames/$name"' EXIT
j() { python3 -c 'import json,sys; r=json.loads(sys.stdin.read().strip().splitlines()[-1]); print(r'"$1"')'; }
has() { local o; o=$(cat); [[ "$o" == *"$1"* ]] || { echo "expected to find: $1 in: $o" >&2; exit 1; }; }
expect() { [[ "$1" == "$2" ]] || { echo "expected $2, got $1" >&2; exit 1; }; }

python3 tools/film.py new "$name" "Test film." | j '["ok"]' | has True
expect "$(python3 tools/film.py check "$name" | j '["next"]')" idea

printf '# %s\n\n**The one sentence:** Test film.\n\n**For:** the test suite\n\n**After it, they:** know the spine works\n\n**Asked for by:** tests/spine.sh\n' "$name" > "$d/idea.md"
printf '# %s: the spec\n\nOne part, one card.\n' "$name" > "$d/spec.md"
printf '# look\n\n| name | colour | means |\n|---|---|---|\n| test | #000000 | test only |\n' > "$d/look.md"
printf '{"facts": [{"id": "secs", "value": 3, "unit": "s", "what": "length", "source": "tests/spine.sh", "measured": "by construction", "when": "now"}]}\n' > "$d/facts.json"
printf '{"format": "beats/1", "parts": [{"id": "only", "dur": 3, "beats": [{"id": "open", "t": 0, "kind": "emotion", "emotion": "open"}, {"id": "card", "t": 0.5, "kind": "title", "text": "3 SECONDS", "until": 2.5, "fact": "secs"}]}]}\n' > "$d/beats.json"
cp tests/fixture/grey.html "$d/scene/scene.html"
ffmpeg -v error -y -f lavfi -i "sine=frequency=440:duration=4" -ac 2 "$d/song/options/tone.wav"
printf '{"file": "options/tone.wav", "said": "the tone"}\n' > "$d/song/pick.json"
expect "$(python3 tools/film.py check "$name" | j '["next"]')" storyboard

echo "a card with an unmeasured number is refused" >&2
sed -i 's/3 SECONDS/4 SECONDS/' "$d/beats.json"
python3 tools/film.py check "$name" | j '["problems"]' | has "no fact"
sed -i 's/4 SECONDS/3 SECONDS/' "$d/beats.json"

echo "a scene that says where its words are: clear, then on the subject" >&2
python3 tools/film.py check "$name" | j '["words"]' | has unchecked
sed -i 's|^window.briefStages = { seek: (id, t) => { frozen = true; render(t); return true; } };|window.briefStages = { seek: (id, t) => { frozen = true; render(t); return true; }, boxes: (t) => [{ kind: "text", id: "clock", x: 760, y: 440, w: 400, h: 100 }, { kind: "subject", id: "bar", x: 160, y: 700, w: 1600, h: 24 }] };|' "$d/scene/scene.html"
python3 tools/film.py check "$name" | j '["words"]' | has "checked"
python3 tools/film.py check "$name" | j '["problems"]' | has "[]"
sed -i 's|y: 440, w: 400, h: 100|y: 650, w: 400, h: 100|' "$d/scene/scene.html"
python3 tools/film.py check "$name" | j '["problems"]' | has "sits on bar"
sed -i 's|y: 650, w: 400, h: 100|y: 440, w: 400, h: 100|' "$d/scene/scene.html"

python3 tools/film.py board "$name" | j '["ok"]' | has True
[[ -s "$d/board.html" && -s "$d/board/sheet.jpg" ]]
python3 tools/film.py draft "$name" --fps 5 --jobs 2 | j '["ok"]' | has True
[[ -s "$d/drafts/draft-1.mp4" && -s "$d/review.html" ]]
expect "$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 "$d/drafts/draft-1.mp4")" audio

echo "notes come back verbatim and block the finish until answered" >&2
printf 'NOTES · %s draft 1\n[card @ 0.50s] first test note\nsecond test note\n' "$name" | python3 tools/moments.py "$name" save - | j '["notes"]' | has 2
cmp -s <(printf 'NOTES · %s draft 1\n[card @ 0.50s] first test note\nsecond test note\n' "$name") "$d/notes/round-1.txt"
expect "$(python3 tools/moments.py "$name" open | j '["ok"]')" False
python3 tools/film.py finish "$name" --said "done" --fps 10 | j '["ok"]' | has False
python3 - "$d/moments.json" <<'PY'
import json, sys
p = sys.argv[1]; m = json.load(open(p))
for mo in m["rounds"][-1]["moments"]:
    mo["answer"] = "changed in the test"
json.dump(m, open(p, "w"))
PY
python3 tools/moments.py "$name" review | j '["ok"]' | has True
grep -q "changed in the test" "$d/review.html"

python3 tools/film.py finish "$name" --said "That is the one." --fps 10 | j '["ok"]' | has True
(cd "$d/finish" && sha256sum -c --quiet SHA256SUMS)
expect "$(python3 -c "import json; print(json.load(open('$d/finish/record.json'))['said'])")" "That is the one."
expect "$(python3 tools/film.py check "$name" | j '["ok"]')" True
echo "spine: every step passed" >&2
