#!/usr/bin/env python3
"""Does every sound land on the frame its picture appears? Measured from the render, never from the plan.

    python3 tools/sync.py <film> [--video <mp4>] [--write-visible]

A beat's sound is written on its second, but a title animates in and an action takes frames to
answer, so a sound placed on the written second plays early. For every beat in beats.json that has
a sound (anything but "none"), this reads the video around the beat's film second:

  picture  the frames, small and grey; the pop is the first frame of the biggest burst of change
           near the beat, where the change first passes half its peak
  sound    the audio's energy every 5 ms; the onset is the first rise past half the biggest rise
           near the beat
  delta    sound minus picture, in ms; negative means the sound is early

A viewer notices sound before its picture from about 45 ms, and sound after it from about 125 ms, so
early and late are judged differently: within one frame is `on`, up to 45 ms early or 125 ms late is
`close`, anything else is `early` or `late`. A beat with no clear burst of change is `no-pop`: a fade
or a slow build has no frame to be early or late against, so look at its frames rather than move it.

--write-visible writes each measured picture second into beats.json as `visible`, and marks the sheet
`measured`. Move a sound by changing where it is written, never by stretching audio or re-rendering
the picture. Needs a render at 24 fps or more: a 5 fps draft cannot resolve 45 ms. Last line is JSON.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import moments  # noqa: E402

W, H, RATE, HOP = 64, 36, 8000, 40     # frame size for change; audio rate; 5 ms hops


def fps_of(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "default=nw=1:nk=1", str(video)], capture_output=True, text=True).stdout.strip().splitlines()[0]
    n, d = r.split("/")
    return float(n) / float(d)


def frames(video: Path, start: float, dur: float) -> list[bytes]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
                          "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return [raw[i:i + W * H] for i in range(0, len(raw) - W * H + 1, W * H)]


def energies(video: Path, start: float, dur: float) -> list[float]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
                          "-vn", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h", raw)
    return [sum(x * x for x in a[i:i + HOP]) / HOP for i in range(0, len(a) - HOP + 1, HOP)]


def onset(series: list[float], floor: float) -> int | None:
    """Index of the first sample of the biggest rise, where it first passes half the rise's peak."""
    if len(series) < 2:
        return None
    rises = [max(0.0, series[i] - series[i - 1]) for i in range(1, len(series))]
    peak = max(rises)
    if peak <= floor:
        return None
    return next(i for i, r in enumerate(rises) if r >= peak / 2) + 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("film")
    ap.add_argument("--video")
    ap.add_argument("--write-visible", action="store_true")
    a = ap.parse_args(argv)
    d = moments.REPO / "films" / a.film
    video = Path(a.video) if a.video else (moments.latest_draft(d) or (None, None))[1]
    if not video or not Path(video).exists():
        print(json.dumps({"ok": False, "wrote": [], "problems": ["no video to measure"]}))
        return 1
    fps = fps_of(video)
    if fps < 24:
        print(json.dumps({"ok": False, "wrote": [], "problems": [f"{video.name} is {fps:g} fps; sync needs 24 fps or more"]}))
        return 1
    frame_ms = 1000 / fps
    beats, _ = moments.film_beats(d)
    rows = []
    for b in beats:
        if not b.get("sound") or b["sound"] == "none":
            continue
        t0 = max(0.0, b["film_t"] - 0.5)
        fr = frames(Path(video), t0, 1.5)
        change = [sum(abs(x - y) for x, y in zip(fr[i], fr[i - 1])) / (W * H) if i else 0.0 for i in range(len(fr))]
        vi = onset(change, 1.0)
        en = [10 * math.log10(e + 1.0) for e in energies(Path(video), t0, 1.5)]
        ai = onset(en, 3.0)
        pic = None if vi is None else round(t0 + vi / fps, 3)
        snd = None if ai is None else round(t0 + ai * HOP / RATE, 3)
        if pic is None:
            verdict, delta = "no-pop", None
        elif snd is None:
            verdict, delta = "no-sound", None
        else:
            delta = round((snd - pic) * 1000)
            verdict = ("on" if abs(delta) <= frame_ms else "close" if -45 <= delta <= 125
                       else "early" if delta < 0 else "late")
        rows.append({"beat": b["id"], "written": b["film_t"], "picture": pic, "sound": snd, "delta_ms": delta, "verdict": verdict})
    if a.write_visible:
        sheet = json.loads((d / "beats.json").read_text())
        found = {r["beat"]: r["picture"] for r in rows if r["picture"] is not None}
        offset = 0.0
        for p in sheet["parts"]:
            for b in p["beats"]:
                if b["id"] in found:
                    b["visible"] = round(found[b["id"]] - offset, 3)
            offset += p["dur"]
        sheet["measured"] = True
        (d / "beats.json").write_text(json.dumps(sheet, indent=2) + "\n")
    off = [r for r in rows if r["verdict"] in ("early", "late")]
    print(json.dumps({"ok": not off, "wrote": [str(d / "beats.json")] if a.write_visible else [], "video": str(video),
                      "fps": fps, "cues": rows, "problems": [f"{r['beat']}: sound {r['delta_ms']} ms off ({r['verdict']})" for r in off]}))
    return 0 if not off else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
