#!/usr/bin/env python3
"""The film's spine: start it, say where it stands, draw its storyboard, draft it, finish it.

    python3 tools/film.py new <name> "<the idea in one sentence>"
    python3 tools/film.py check <name>
    python3 tools/film.py board <name>
    python3 tools/film.py draft <name> [--fps 5] [--jobs 4]
    python3 tools/film.py finish <name> --said "<the person's words, verbatim>" [--fps 60] [--poster <second>]

Everything lives in films/<name>/ (protocol/build-order.md). `check` reads which files exist and says
which step is next, and refuses a scene that loads anything from outside, a beat sheet that does not
check, a card showing a number that is not in facts.json, and notes with no answer. `board` draws one
frame per beat from the real scene. `draft` renders at 5 fps in parallel slices, puts the picked sound
under it, and writes the review page. `finish` renders at full rate, encodes, measures, and writes the
record, checksums and a poster. Every command ends with one JSON line.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import moments  # noqa: E402
from notespage import page  # noqa: E402

OUTSIDE = re.compile(r"""(?:src|href)\s*=\s*["']https?://|url\(\s*["']?https?://|fetch\(\s*["'`]https?://|@import\s+["']?https?://|import\s*\(?\s*["']https?://""")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

SCENE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{name}</title>
<!-- The scene for {name}. One clock: render(t) draws the whole frame for second t, and nothing else
     moves the picture. See protocol/contract.md. Nothing is drawn yet: the look is yours to invent
     (protocol/look.md), written in look.md before you draw. -->
<style>html,body{{margin:0;background:#000;overflow:hidden}}canvas{{display:block;width:100vw;height:100vh;object-fit:contain}}</style>
</head><body><canvas id="stage" width="1920" height="1080"></canvas>
<script>
const W = 1920, H = 1080, END = {end};
const ctx = document.getElementById('stage').getContext('2d');
function rng(seed) {{ return () => {{ seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }}; }}

function render(t) {{
  ctx.clearRect(0, 0, W, H);
  // draw the frame for second t here
}}

let frozen = false, start = performance.now();
window.briefStages = {{ seek: (id, t) => {{ frozen = true; render(t); return true; }} }};
const q = new URLSearchParams(location.search);
if (q.has('t')) {{ frozen = true; render(+q.get('t')); }}
else (function loop() {{ if (!frozen) {{ render(((performance.now() - start) / 1000) % END); requestAnimationFrame(loop); }} }})();
document.addEventListener('click', () => {{ frozen = !frozen; }});
</script></body></html>
"""


def out(**fields) -> int:
    fields = {"ok": True, "wrote": [], "problems": [], **fields}
    print(json.dumps(fields))
    return 0 if fields["ok"] else 1


def run_json(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    lines = [l for l in p.stdout.strip().splitlines() if l.startswith("{")]
    try:
        r = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        r = {"ok": False, "problems": [f"{Path(cmd[1]).name}: no result line; stderr: {p.stderr.strip()[-300:]}"]}
    return r


def film(name: str) -> Path:
    return REPO / "films" / name


def scene_url(d: Path) -> str:
    return (d / "scene" / "scene.html").resolve().as_uri()


def unfilled(path: Path) -> bool:
    return not path.exists() or bool(re.search(r"<[a-z][^>]*>", path.read_text())) and path.suffix == ".md"


def cmd_new(name: str, idea: str) -> int:
    d = film(name)
    if d.exists():
        return out(ok=False, problems=[f"{d} already exists"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        return out(ok=False, problems=["a film's name is lowercase words joined by hyphens"])
    (d / "scene").mkdir(parents=True)
    for sub in ("song/options", "notes", "drafts", "finish"):
        (d / sub).mkdir(parents=True)
    tpl = REPO / "templates"
    (d / "idea.md").write_text((tpl / "idea.md").read_text().replace("<film name>", name)
                               .replace("<what this film tells, in one sentence a stranger understands>", idea))
    for f in ("spec.md", "look.md"):
        (d / f).write_text((tpl / f).read_text().replace("<film name>", name))
    (d / "facts.json").write_text(json.dumps({"facts": []}, indent=2) + "\n")
    (d / "beats.json").write_text(json.dumps({"format": "beats/1", "parts": []}, indent=2) + "\n")
    (d / "scene" / "scene.html").write_text(SCENE.format(name=name, end=10))
    return out(wrote=[str(d)], next="idea: finish idea.md, then measure (protocol/build-order.md)")


def number_problems(d: Path) -> list[str]:
    facts = {f["id"]: f for f in json.loads((d / "facts.json").read_text()).get("facts", [])}
    values = {str(f.get("value")).replace(",", "") for f in facts.values()}
    probs = []
    for b, _ in [(b, 0) for b in moments.film_beats(d)[0] if b.get("kind") == "title"]:
        for n in NUMBER.findall(b.get("text", "")):
            n = n.replace(",", "").rstrip(".")
            want = str(facts[b["fact"]]["value"]).replace(",", "") if b.get("fact") in facts else None
            if (want is not None and n != want) or (want is None and n not in values):
                probs.append(f"card {b['id']} shows {n}, which no fact in facts.json holds")
    return probs


def word_problems(d: Path) -> tuple[list[str], bool]:
    """Ask the scene where its words and its subject are at the middle of every title, if it says.

    A scene may expose briefStages.boxes(t) -> [{kind: "text" | "subject", x, y, w, h, id?}] in frame pixels
    (protocol/contract.md). Words must sit inside the frame and off the subject. A scene that does not expose it
    is unchecked, which is reported as such and never as a pass."""
    beats, _ = moments.film_beats(d)
    secs = [round((b["film_t"] + b["film_t"] - b["t"] + b["until"]) / 2, 3) for b in beats if b.get("kind") == "title" and b.get("until")]
    if not secs:
        return [], True
    expr = ("(() => { if (!window.briefStages || typeof briefStages.boxes !== 'function') return null; const out = {};"
            f" for (const t of {json.dumps(secs)}) {{ briefStages.seek('stage', t); out[t] = briefStages.boxes(t); }} return out; }})()")
    r = run_json(["node", "tools/pagecheck.mjs", scene_url(d), expr, "20"])
    boxes = r.get("value")
    if boxes is None:
        return [], False
    probs = []
    W, H = 1920, 1080
    for t, bs in boxes.items():
        texts = [b for b in bs if b.get("kind") == "text"]
        subjects = [b for b in bs if b.get("kind") == "subject"]
        for b in texts:
            label = b.get("id", "words")
            if b["x"] < 0 or b["y"] < 0 or b["x"] + b["w"] > W or b["y"] + b["h"] > H:
                probs.append(f"at {t} s, {label} runs outside the frame")
            for sb in subjects:
                if b["x"] < sb["x"] + sb["w"] and sb["x"] < b["x"] + b["w"] and b["y"] < sb["y"] + sb["h"] and sb["y"] < b["y"] + b["h"]:
                    probs.append(f"at {t} s, {label} sits on {sb.get('id', 'the subject')}")
    return probs, True


def cmd_check(name: str) -> int:
    d = film(name)
    if not d.is_dir():
        return out(ok=False, problems=[f"no film at {d}"])
    problems, done = [], []
    steps = [
        ("idea", lambda: not unfilled(d / "idea.md")),
        ("measure", lambda: (d / "facts.json").exists()),
        ("spec", lambda: not unfilled(d / "spec.md")),
        ("look", lambda: (d / "look.md").exists() and "| | | |" not in (d / "look.md").read_text()),
        ("beats", lambda: run_json(["node", "tools/beats.mjs", "check", str(d / "beats.json"), str(d / "facts.json")]).get("ok")),
        ("sound", lambda: (d / "song" / "pick.json").exists()),
        ("storyboard", lambda: (d / "board.html").exists()),
        ("draft", lambda: moments.latest_draft(d) is not None),
        ("notes", lambda: moments.open_notes(name)["ok"]),
        ("finish", lambda: (d / "finish" / "record.json").exists()),
    ]
    nxt = None
    for step, test in steps:
        try:
            ok = bool(test())
        except Exception as e:   # a malformed file is a step not done, with the reason
            ok = False
            problems.append(f"{step}: {e}")
        if ok:
            done.append(step)
        elif nxt is None:
            nxt = step
    scene = d / "scene" / "scene.html"
    if scene.exists():
        for n, line in enumerate(scene.read_text().splitlines(), 1):
            if OUTSIDE.search(line):
                problems.append(f"scene line {n} loads something from outside (protocol/contract.md)")
        r = run_json(["node", "tools/pagecheck.mjs", scene_url(d), "typeof window.briefStages.seek", "20"])
        if r.get("value") != "function":
            problems.append("the scene does not expose window.briefStages.seek")
    words_checked = None
    if "beats" in done:
        problems += number_problems(d)
        if scene.exists():
            wp, words_checked = word_problems(d)
            problems += wp
    left = moments.open_notes(name)["open"] if (d / "moments.json").exists() else []
    if left:
        problems.append(f"{len(left)} notes have no answer: python3 tools/moments.py {name} open")
    return out(ok=not problems, done=done, next=nxt, problems=problems,
               words=("checked" if words_checked else "unchecked: the scene does not expose briefStages.boxes(t)") if words_checked is not None else None)


def stills_at(d: Path, seconds: list[float], outdir: Path) -> dict:
    return run_json(["node", "tools/stills.mjs", scene_url(d), str(outdir), *[f"{s:.3f}" for s in seconds]])


def cmd_board(name: str) -> int:
    d = film(name)
    beats, total = moments.film_beats(d)
    if not beats:
        return out(ok=False, problems=["beats.json has no beats yet"])
    shots = d / "board"
    r = stills_at(d, sorted({b["film_t"] for b in beats}), shots)
    if not r.get("ok"):
        return out(ok=False, problems=r.get("problems", ["stills failed"]))
    items = [{"id": b["id"], "label": f"{b['kind']} · {b.get('text') or b.get('what') or b['id']}", "t": b["film_t"],
              "img": f"board/s_{b['film_t']:09.3f}.jpg", "text": b.get("what")} for b in beats]
    html = page(f"{name}: storyboard", f"One frame per beat, drawn by the film's own scene. {total:.1f} s. "
                "Leave a note on anything, then press Copy notes and paste the text to your agent.", items,
                heading=f"{name} storyboard")
    (d / "board.html").write_text(html)
    return out(wrote=[str(d / "board.html"), str(shots / "sheet.jpg")])


def render_parallel(d: Path, frames: Path, fps: int, end: float, jobs: int) -> list[str]:
    n = round(end * fps) + 1
    edges = [round(i * n / jobs) for i in range(jobs + 1)]
    procs = [subprocess.Popen(["node", "tools/slices.mjs", scene_url(d), str(frames), str(fps), str(end),
                               str(edges[i]), str(edges[i + 1]), "1920", "1080"], cwd=REPO,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
             for i in range(jobs) if edges[i + 1] > edges[i]]
    problems = []
    for p in procs:
        line = (p.communicate()[0].strip().splitlines() or ["{}"])[-1]
        r = json.loads(line) if line.startswith("{") else {"ok": False, "problems": ["no result"]}
        if not r.get("ok"):
            problems += r.get("problems", ["a slice failed"])
    have = len(list(frames.glob("f*.jpg")))
    if have != n:
        problems.append(f"{have} of {n} frames on disk")
    return problems


def sound_of(d: Path) -> Path | None:
    p = d / "song" / "pick.json"
    if not p.exists():
        return None
    pick = json.loads(p.read_text())
    return None if pick.get("silent") else (d / "song" / pick["file"]).resolve()


def encode(frames: Path, fps: int, end: float, audio: Path | None, out_mp4: Path, crf: int, preset: str) -> list[str]:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps), "-i", str(frames / "f%05d.jpg")]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k", "-t", f"{end + 1 / fps:.3f}"]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return [p.stderr.strip()[-300:] or "ffmpeg failed"] if p.returncode else []


def frames_dir(d: Path, label: str) -> Path:
    base = Path(os.environ.get("CINEMA_FRAMES", REPO / ".frames"))
    f = base / d.name / label
    shutil.rmtree(f, ignore_errors=True)
    f.mkdir(parents=True)
    return f


def cmd_draft(name: str, fps: int, jobs: int) -> int:
    d = film(name)
    beats, total = moments.film_beats(d)
    if total <= 0:
        return out(ok=False, problems=["beats.json has no length yet"])
    last = moments.latest_draft(d)
    n = (last[0] if last else 0) + 1
    frames = frames_dir(d, f"draft-{n}")
    problems = render_parallel(d, frames, fps, total, jobs)
    mp4 = d / "drafts" / f"draft-{n}.mp4"
    if not problems:
        problems = encode(frames, fps, total, sound_of(d), mp4, 23, "veryfast")
    shutil.rmtree(frames, ignore_errors=True)
    if problems:
        return out(ok=False, problems=problems)
    stills_at(d, sorted({b["film_t"] for b in beats}), d / "drafts" / f"draft-{n}-stills")
    r = moments.review(name)
    check = run_json(["python3", "tools/deliver.py", str(d / "review.html"), str(mp4)])
    return out(ok=r["ok"] and check.get("ok", False), wrote=[str(mp4), str(d / "review.html")], draft=n, fps=fps,
               seconds=total, sound=str(sound_of(d)) if sound_of(d) else None, problems=r["problems"] + check.get("problems", []))


def loudness(path: Path) -> dict:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", p.stderr)
    return {"integrated_lufs": float(i[-1]) if i else None, "true_peak_dbtp": float(tp[-1]) if tp else None}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_finish(name: str, said: str, fps: int, poster: float | None, jobs: int) -> int:
    d = film(name)
    if not said.strip():
        return out(ok=False, problems=["finish needs the person's words saying it is done, verbatim (--said)"])
    beats, total = moments.film_beats(d)
    left = moments.open_notes(name)["open"] if (d / "moments.json").exists() else []
    if left:
        return out(ok=False, problems=[f"{len(left)} notes have no answer"])
    fin = d / "finish"
    fin.mkdir(exist_ok=True)
    frames = frames_dir(d, "finish")
    problems = render_parallel(d, frames, fps, total, jobs)
    mp4 = fin / f"{name}-16x9.mp4"
    audio = sound_of(d)
    if not problems:
        problems = encode(frames, fps, total, audio, mp4, 16, "slow")
    shutil.rmtree(frames, ignore_errors=True)
    if problems:
        return out(ok=False, problems=problems)
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,nb_frames",
                                       "-of", "json", str(mp4)], capture_output=True, text=True).stdout)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    measured = {"seconds": float(probe["format"]["duration"]), "width": v["width"], "height": v["height"],
                "frames": int(v.get("nb_frames", 0)) or None, "audio": any(s["codec_type"] == "audio" for s in probe["streams"])}
    if audio:
        measured.update(loudness(mp4))
    at = poster if poster is not None else round(total / 2, 2)
    p_out = fin / f"{name}.poster.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", str(mp4), "-frames:v", "1", "-vf", "scale=720:-1", str(p_out)])
    sources = sorted(p for p in d.rglob("*") if p.is_file() and p.parent.name not in ("finish", "board")
                     and "drafts" not in p.parts and p.suffix in (".html", ".js", ".json", ".md", ".css"))
    record = {"film": name, "said": said, "finished": time.strftime("%Y-%m-%d"), "fps": fps, "measured": measured,
              "sound": {"file": str(audio.relative_to(d)), "sha256": sha(audio)} if audio else None,
              "sources": {str(p.relative_to(d)): sha(p) for p in sources},
              "rebuild": f"python3 tools/film.py finish {name} --said <words> --fps {fps}" + (f" --poster {poster}" if poster is not None else "")}
    (fin / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    html = page(f"{name}", f"Finished {record['finished']}. {measured['seconds']:.1f} s at {fps} fps.", [], film=mp4.name, heading=f"{name} finished")
    (fin / "review.html").write_text(html)
    sums = "".join(f"{sha(p)}  {p.name}\n" for p in sorted(fin.iterdir()) if p.is_file() and p.name != "SHA256SUMS")
    (fin / "SHA256SUMS").write_text(sums)
    check = run_json(["python3", "tools/deliver.py", str(fin / "review.html"), str(mp4)])
    return out(ok=check.get("ok", False), wrote=[str(mp4), str(fin / "record.json"), str(p_out), str(fin / "SHA256SUMS")],
               measured=measured, problems=check.get("problems", []))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["new", "check", "board", "draft", "finish"])
    ap.add_argument("name")
    ap.add_argument("idea", nargs="?")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--said", default="")
    ap.add_argument("--poster", type=float)
    a = ap.parse_args(argv)
    if a.cmd == "new":
        return cmd_new(a.name, a.idea or "") if a.idea else out(ok=False, problems=["new needs the idea in one sentence"])
    if a.cmd == "check":
        return cmd_check(a.name)
    if a.cmd == "board":
        return cmd_board(a.name)
    if a.cmd == "draft":
        return cmd_draft(a.name, a.fps or 5, a.jobs)
    return cmd_finish(a.name, a.said, a.fps or 60, a.poster, a.jobs)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
