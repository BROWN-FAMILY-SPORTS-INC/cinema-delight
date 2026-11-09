#!/usr/bin/env python3
"""The public leak check: things that should never be in this repository, whoever wrote them.

    python3 tests/check_leaks.py [root]

Looks at every file git tracks (or every file under root, outside git) for: a home-directory path,
an email address, the shape of an API key or token, any audio or video file, any image over 200 KB,
and any outside URL inside a scene. Exit 1 on any finding; the last line is JSON.

It knows no names. Keeping a particular person's or project's names out is a separate check that
whoever exports into this repository runs on their side.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
MEDIA = {".mp4", ".mov", ".webm", ".mkv", ".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aiff"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT = {".md", ".py", ".mjs", ".js", ".sh", ".html", ".css", ".json", ".txt", ".yml", ".yaml", ".toml", ""}
PATTERNS = {
    "home path": re.compile(r"/(?:home|Users)/[a-z][a-z0-9_-]+/"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "key or token": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|sk-or-v1-[a-f0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})"),
}
SCENE_URL = re.compile(r"""(?:src|href)\s*=\s*["']https?://|url\(\s*["']?https?://|fetch\(\s*["']https?://|@import\s+["']?https?://""")
ALLOW_EMAIL = {"noreply@github.com"}


def tracked(root: Path) -> list[Path]:
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
        return [root / p for p in out.decode().split("\0") if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def main() -> int:
    findings = []
    for p in tracked(ROOT):
        if not p.exists():
            continue
        rel = p.relative_to(ROOT).as_posix()
        ext = p.suffix.lower()
        if ext in MEDIA:
            findings.append({"file": rel, "what": "audio or video file"})
            continue
        if ext in IMAGES and p.stat().st_size > 200_000:
            findings.append({"file": rel, "what": f"image over 200 KB ({p.stat().st_size} bytes)"})
            continue
        if ext not in TEXT:
            continue
        text = p.read_text(errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for what, rx in PATTERNS.items():
                for m in rx.finditer(line):
                    if what == "email" and m.group(0) in ALLOW_EMAIL:
                        continue
                    findings.append({"file": rel, "line": n, "what": what, "text": m.group(0)})
            if ext == ".html" and SCENE_URL.search(line):
                findings.append({"file": rel, "line": n, "what": "outside URL in a scene"})
    for f in findings:
        print(f"{f['file']}:{f.get('line', '-')}  {f['what']}" + (f"  {f['text']}" if "text" in f else ""), file=sys.stderr)
    print(json.dumps({"ok": not findings, "wrote": [], "problems": findings}))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
