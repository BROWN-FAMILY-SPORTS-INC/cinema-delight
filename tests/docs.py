#!/usr/bin/env python3
"""Every repository path the documents mention exists. A method that points at a missing tool sends an agent nowhere."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = re.compile(r"(?<![\w/.-])((?:tools|protocol|templates|kit|tests|skill)/[\w./-]+\.(?:md|py|mjs|js|sh|json|html))")
missing = []
for doc in [*ROOT.glob("*.md"), *ROOT.glob("protocol/*.md"), *ROOT.glob("skill/*.md"), *ROOT.glob("tools/*"), *ROOT.glob("kit/**/*.js")]:
    if not doc.is_file():
        continue
    for n, line in enumerate(doc.read_text(errors="replace").splitlines(), 1):
        for ref in REF.findall(line):
            if not (ROOT / ref).exists():
                missing.append(f"{doc.relative_to(ROOT)}:{n} mentions {ref}")
for m in missing:
    print(m, file=sys.stderr)
print(json.dumps({"ok": not missing, "wrote": [], "problems": missing}))
sys.exit(1 if missing else 0)
