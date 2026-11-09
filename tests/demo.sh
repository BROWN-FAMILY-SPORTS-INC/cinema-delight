#!/usr/bin/env bash
# The demo kit: capture a real shell command, check what it drew, then draw the capture, a key and the pointer in a
# self-contained scene, and render and probe it. The capture needs uv (for pyte); without it that part is skipped, and
# said so.
set -eu   # no pipefail: results are judged by has
cd "$(dirname "$0")/.."
w="$(mktemp -d)"; trap 'rm -rf "$w"' EXIT
has() { local o; o=$(cat); [[ "$o" == *"$1"* ]] || { echo "expected to find: $1 in: $o" >&2; exit 1; }; }

echo "the frame refuses to draw without a look" >&2
node -e "require('./kit/demo/frame.js'); try { DEMO.drawKey({save(){}}, 'A', 0, 0, 0, {}); process.exit(1) } catch (e) { if (!/look must give/.test(e.message)) process.exit(1) }"

if command -v uv >/dev/null; then
  echo "a real program, captured" >&2
  cat > "$w/session.json" <<JSON
{ "cols": 60, "rows": 8, "fps": 10, "cwd": "$w", "cmd": ["bash", "--noprofile", "--norc"],
  "palette": { "fg": "#808080", "bg": "#000000", "colors": ["#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080","#808080"] },
  "steps": [ {"wait": 0.3}, {"type": "echo captured for real\r", "cps": 40}, {"wait_quiet": 0.5, "timeout": 10}, {"mark": "said"} ],
  "tail": 0.5 }
JSON
  uv run --quiet tools/tty_capture.py "$w/session.json" "$w/capture.json" >/dev/null 2>&1
  end=$(python3 -c "import json; print(json.load(open('$w/capture.json'))['dur'])")
  uv run --quiet tools/tty_capture.py --text "$w/capture.json" "$end" 2>/dev/null | has "captured for real"
else
  echo "SKIPPED: the real capture (uv is not installed)" >&2
  python3 -c "
import json
row=[[0,'captured for real','default','default',0]]
json.dump({'cols':60,'rows':8,'fps':10,'palette':{'fg':'#808080','bg':'#000000','colors':['#808080']*16},'table':[[],row],
           'frames':[[0,[1]+[0]*7,0,1,True]],'marks':[],'keys':[],'dur':1}, open('$w/capture.json','w'))"
fi

echo "a scene draws the capture, a key and the pointer" >&2
python3 - "$w" <<'PY'
import json, sys
from pathlib import Path
w = Path(sys.argv[1])
# placeholder values: every colour the same test grey, so nothing here reads as a look
look = {k: "#808080" for k in ("keyFace", "keyInk", "keyEdge", "pointer", "ring")} | {"face": "monospace", "keySize": 64}
html = f"""<!doctype html><html><head><meta charset=utf-8><style>html,body{{margin:0;background:#000}}</style></head><body>
<canvas id=stage width=1920 height=1080></canvas>
<script>{Path('kit/demo/frame.js').read_text()}</script><script>{Path('kit/demo/tty.js').read_text()}</script>
<script>
const CAP = {(w/'capture.json').read_text()}, L = {json.dumps(look)};
const c = document.getElementById('stage').getContext('2d'), lay = DEMO.layout(1920, 1080);
function render(t) {{
  c.clearRect(0, 0, 1920, 1080);
  TTY.draw(c, lay.ui.x, lay.ui.y, lay.ui.w, lay.ui.h * 0.5, CAP, Math.min(t, CAP.dur), {{ face: L.face }});
  DEMO.drawKey(c, 'Enter', lay.words.x, lay.words.y + 200, DEMO.press(t, 1.0), L);
  const [x, y] = DEMO.drag(t, 0.5, 1, [lay.ui.x, lay.ui.y + 600], [lay.ui.x + 400, lay.ui.y + 700]);
  DEMO.drawPointer(c, x, y, t, 1.5, L);
}}
window.briefStages = {{ seek: (id, t) => {{ render(t); return true; }} }};
</script></body></html>"""
(w / "demo.html").write_text(html)
PY
node tools/state-probe.mjs "file://$w/demo.html" 0 1 1.6 2 | python3 -c 'import json,sys; r=json.loads(sys.stdin.read().strip().splitlines()[-1]); assert r["ok"], r'
node tools/render.mjs "file://$w/demo.html" "$w/frames" 5 2 | has '"ok":true'
echo "demo: every check passed" >&2
