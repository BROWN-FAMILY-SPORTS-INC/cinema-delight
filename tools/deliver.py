#!/usr/bin/env python3
"""Refuse a review page whose film will not play.

    python3 tools/deliver.py <review.html> <film.mp4> [<film.mp4> ...]

Checks that the page is a local HTML file, that it embeds each film exactly once in a <video> with
controls, and that each film is a non-empty MP4 with a video stream and a measured positive
duration. A review page that links a film instead of playing it, or plays a broken one, wastes the
person's attention. Last line of output is JSON.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Review(HTMLParser):
    def __init__(self):
        super().__init__()
        self.videos, self.active = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "video":
            self.active = {"controls": "controls" in a, "sources": [a["src"]] if a.get("src") else []}
            self.videos.append(self.active)
        elif tag == "source" and self.active is not None and a.get("src"):
            self.active["sources"].append(a["src"])

    def handle_endtag(self, tag):
        if tag == "video":
            self.active = None


def local(value: str, page: Path) -> Path | None:
    u = urlsplit(value)
    if u.scheme == "file":
        return Path(unquote(u.path)).resolve()
    if not u.scheme and not u.netloc:
        return (page.parent / unquote(u.path)).resolve()
    return None


def check(page: Path, films: list[Path]) -> list[dict]:
    page = page.resolve()
    if page.suffix.lower() != ".html" or not page.is_file():
        raise ValueError("the review must be an existing HTML file")
    r = Review()
    r.feed(page.read_text())
    out = []
    for film in (f.resolve() for f in films):
        if film.suffix.lower() != ".mp4" or not film.is_file() or not film.stat().st_size:
            raise ValueError(f"not a non-empty MP4: {film}")
        embeds = [v for v in r.videos if film in [local(s, page) for s in v["sources"]]]
        if len(embeds) != 1 or not embeds[0]["controls"]:
            raise ValueError(f"the page must embed {film.name} once, in a video with controls")
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                                           "-of", "json", str(film)], capture_output=True, text=True, check=True).stdout)
        seconds = float(probe["format"].get("duration", "nan"))
        if not any(s.get("codec_type") == "video" for s in probe["streams"]):
            raise ValueError(f"no video stream: {film}")
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(f"no measurable duration: {film}")
        out.append({"film": str(film), "seconds": round(seconds, 3), "bytes": film.stat().st_size,
                    "audio": any(s.get("codec_type") == "audio" for s in probe["streams"])})
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        print(json.dumps({"ok": False, "wrote": [], "problems": ["usage"]}))
        return 2
    try:
        films = check(Path(argv[0]), [Path(a) for a in argv[1:]])
        print(json.dumps({"ok": True, "wrote": [], "films": films, "problems": []}))
        return 0
    except (ValueError, subprocess.CalledProcessError) as e:
        print(json.dumps({"ok": False, "wrote": [], "problems": [str(e)]}))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
