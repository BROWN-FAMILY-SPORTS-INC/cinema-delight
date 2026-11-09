#!/usr/bin/env python3
"""Bring finished audio to a loudness and a true-peak ceiling, and measure that it got there.

    python3 tools/master.py <in> <out.wav> [--lufs -16] [--tp -1] [--lra 11]

Two passes of ffmpeg's loudnorm: the first measures, the second applies one linear gain, so the
music's own dynamics stay. Then the result is measured again (integrated loudness and true peak,
which is the peak between samples that a lossy encode or a converter will rebuild; a sample ceiling
alone leaves true peaks over it). If linear gain cannot reach the target without passing the
ceiling, loudnorm falls back to dynamic mode, and the report says so. Last line of output is JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys


def measure(path: str, lufs: float, tp: float, lra: float) -> dict:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                        f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[\s\S]*?\}", p.stderr[p.stderr.rfind("[Parsed_loudnorm"):])
    if not m:
        raise RuntimeError("loudnorm printed no measurement: " + p.stderr[-300:])
    return json.loads(m.group(0))


def reading(path: str) -> dict:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    t = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", p.stderr)
    return {"integrated_lufs": float(i[-1]) if i else None, "true_peak_dbtp": float(t[-1]) if t else None}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--tp", type=float, default=-1.0)
    ap.add_argument("--lra", type=float, default=11.0)
    a = ap.parse_args(argv)
    try:
        m = measure(a.src, a.lufs, a.tp, a.lra)
        af = (f"loudnorm=I={a.lufs}:TP={a.tp}:LRA={a.lra}:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
              f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:print_format=json")
        p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", a.src, "-af", af, "-ar", "48000", "-c:a", "pcm_f32le", a.out],
                           capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(p.stderr[-300:])
        mode = re.findall(r'"normalization_type"\s*:\s*"(\w+)"', p.stderr)
        after = reading(a.out)
        problems = []
        if after["true_peak_dbtp"] is not None and after["true_peak_dbtp"] > a.tp + 0.1:
            problems.append(f"true peak {after['true_peak_dbtp']} dBTP is over the {a.tp} ceiling")
        print(json.dumps({"ok": not problems, "wrote": [a.out], "before": {"integrated_lufs": float(m["input_i"]),
                          "true_peak_dbtp": float(m["input_tp"])}, "after": after,
                          "mode": mode[-1] if mode else None, "problems": problems}))
        return 0 if not problems else 1
    except (RuntimeError, KeyError, ValueError) as e:
        print(json.dumps({"ok": False, "wrote": [], "problems": [str(e)]}))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
