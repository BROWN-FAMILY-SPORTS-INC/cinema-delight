#!/usr/bin/env python3
"""The notes loop: a review page for the latest draft, and the person's notes brought back.

    python3 tools/moments.py <film> review          # write films/<film>/review.html for the latest draft
    python3 tools/moments.py <film> save <file|->   # save pasted notes verbatim, and add them to moments.json
    python3 tools/moments.py <film> open            # list notes that have no answer yet

A review page shows the draft with controls, one item per beat (its frame from the draft's contact
sheet, at its film second), last round's notes with your answers, and a note box on everything.
The person's Copy notes text comes back to you; `save` writes it to notes/round-N.txt exactly as
pasted, and adds one moment per note to moments.json with their words and the second it names.
Fill each moment's `answer` with what you changed, or why nothing changed. A note with no answer
is still open, and `film.py check` says so. Last line of output is JSON.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notespage import page  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
LINE = re.compile(r"^\[(?P<id>[^\]@]+?)(?:\s*@\s*(?P<t>[\d.]+)s)?\]\s*(?P<said>.+)$")


def film_dir(name: str) -> Path:
    d = REPO / "films" / name
    if not d.is_dir():
        raise SystemExit(json.dumps({"ok": False, "wrote": [], "problems": [f"no film at {d}"]}))
    return d


def film_beats(d: Path) -> tuple[list[dict], float]:
    sheet = json.loads((d / "beats.json").read_text())
    out, offset = [], 0.0
    for p in sheet["parts"]:
        for b in p["beats"]:
            out.append({**b, "part": p["id"], "film_t": round(offset + b["t"], 3)})
        offset += p["dur"]
    return out, offset


def latest_draft(d: Path) -> tuple[int, Path] | None:
    drafts = sorted((int(m.group(1)), p) for p in (d / "drafts").glob("draft-*.mp4") if (m := re.search(r"draft-(\d+)", p.name)))
    return drafts[-1] if drafts else None


def load_moments(d: Path) -> dict:
    p = d / "moments.json"
    return json.loads(p.read_text()) if p.exists() else {"rounds": []}


def review(name: str) -> dict:
    d = film_dir(name)
    found = latest_draft(d)
    if not found:
        return {"ok": False, "wrote": [], "problems": ["no draft yet: python3 tools/film.py draft " + name]}
    n, film = found
    beats, total = film_beats(d)
    sheet = d / "drafts" / f"draft-{n}-stills"
    items = []
    for b in beats:
        still = sheet / f"s_{b['film_t']:09.3f}.jpg"
        label = b.get("text") or b.get("what") or b["id"]
        items.append({"id": b["id"], "label": f"{b['kind']} · {label}", "t": b["film_t"],
                      "img": str(still.relative_to(d)) if still.exists() else None, "text": b.get("what")})
    m = load_moments(d)
    if m["rounds"]:
        last = m["rounds"][-1]
        for mo in last["moments"]:
            items.insert(0, {"id": f"answer-{mo['id']}", "label": f"Last round you said: {mo['said']}",
                             "t": mo.get("t"), "text": "What came of it: " + (mo.get("answer") or "not answered yet")})
    html = page(f"{name}: draft {n}", f"Draft {n}, {total:.1f} s. Leave a note on anything, then press Copy notes and paste the text to your agent.",
                items, film=str(film.relative_to(d)), heading=f"{name} draft {n}")
    out = d / "review.html"
    out.write_text(html)
    return {"ok": True, "wrote": [str(out)], "draft": n, "problems": []}


def save(name: str, src: str) -> dict:
    d = film_dir(name)
    text = sys.stdin.read() if src == "-" else Path(src).read_text()
    m = load_moments(d)
    n = len(m["rounds"]) + 1
    notes = d / "notes"
    notes.mkdir(exist_ok=True)
    raw = notes / f"round-{n}.txt"
    raw.write_text(text)   # verbatim: their words are the record
    beats = {b["id"]: b for b in film_beats(d)[0]}
    moments, unread = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("NOTES"):
            continue
        g = LINE.match(line)
        if not g:
            unread.append(line)
            continue
        bid = g["id"].strip()
        t = float(g["t"]) if g["t"] else beats.get(bid, {}).get("film_t")
        moments.append({"id": f"r{n}-{len(moments) + 1}", "on": bid, "said": g["said"].strip(), "t": t,
                        "frame": (beats.get(bid) or {}).get("what"), "answer": ""})
    for line in unread:   # a line with no tag is still their words
        moments.append({"id": f"r{n}-{len(moments) + 1}", "on": "page", "said": line, "t": None, "frame": None, "answer": ""})
    draft = latest_draft(d)
    m["rounds"].append({"round": n, "notes_file": str(raw.relative_to(d)), "on_draft": draft[0] if draft else None,
                        "moments": moments})
    (d / "moments.json").write_text(json.dumps(m, indent=2) + "\n")
    return {"ok": True, "wrote": [str(raw), str(d / "moments.json")], "round": n, "notes": len(moments), "problems": []}


def open_notes(name: str) -> dict:
    d = film_dir(name)
    m = load_moments(d)
    left = [mo for r in m["rounds"] for mo in r["moments"] if not mo.get("answer")]
    return {"ok": not left, "wrote": [], "open": left, "problems": [f"{len(left)} notes have no answer"] if left else []}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("review", "save", "open") or (argv[1] == "save" and len(argv) < 3):
        print(__doc__, file=sys.stderr)
        print(json.dumps({"ok": False, "wrote": [], "problems": ["usage"]}))
        return 2
    r = review(argv[0]) if argv[1] == "review" else save(argv[0], argv[2]) if argv[1] == "save" else open_notes(argv[0])
    print(json.dumps(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
