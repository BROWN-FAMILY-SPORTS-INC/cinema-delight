#!/usr/bin/env python3
"""The sound options, side by side, for the person to pick from; and their pick, kept verbatim.

    python3 tools/options.py <film> page
    python3 tools/options.py <film> pick <options/file.wav> --said "<their words>"
    python3 tools/options.py <film> silent --said "<their words>"

`page` writes films/<film>/song/options.html: the essay at the top, then every audio file in
song/options/ with a player and a note box, and Copy notes. `pick` records which option the person
chose, in their words, to song/pick.json, which the draft puts under the picture. A pick can be a
file you made by mixing two options when that is what they asked for; record what they said.
Last line of output is JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from notespage import page  # noqa: E402

REPO = TOOLS.parent
AUDIO = {".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("film")
    ap.add_argument("cmd", choices=["page", "pick", "silent"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--said", default="")
    a = ap.parse_args(argv)
    song = REPO / "films" / a.film / "song"
    if not song.is_dir():
        print(json.dumps({"ok": False, "wrote": [], "problems": [f"no film at {song.parent}"]}))
        return 1
    if a.cmd == "page":
        opts = sorted(p for p in (song / "options").glob("*") if p.suffix.lower() in AUDIO)
        if not opts:
            print(json.dumps({"ok": False, "wrote": [], "problems": ["no audio in song/options/"]}))
            return 1
        essay = (song / "essay.md").read_text() if (song / "essay.md").exists() else None
        items = ([{"id": "essay", "label": "The essay these were made from", "text": essay}] if essay else [])
        items += [{"id": p.stem, "label": p.name, "audio": f"options/{p.name}"} for p in opts]
        out = song / "options.html"
        out.write_text(page(f"{a.film}: sound options", "Play each one. Say which you want, or which parts of which, "
                            "then press Copy notes and paste the text to your agent.", items, heading=f"{a.film} sound options"))
        print(json.dumps({"ok": True, "wrote": [str(out)], "options": [p.name for p in opts], "problems": []}))
        return 0
    if not a.said.strip():
        print(json.dumps({"ok": False, "wrote": [], "problems": ["a pick needs the person's words, verbatim (--said)"]}))
        return 1
    if a.cmd == "silent":
        pick = {"silent": True, "said": a.said}
    else:
        f = (song / a.file).resolve() if a.file else None
        if not f or not f.is_file():
            print(json.dumps({"ok": False, "wrote": [], "problems": [f"no such file under song/: {a.file}"]}))
            return 1
        pick = {"file": str(f.relative_to(song)), "said": a.said}
    (song / "pick.json").write_text(json.dumps(pick, indent=2) + "\n")
    print(json.dumps({"ok": True, "wrote": [str(song / "pick.json")], "problems": []}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
