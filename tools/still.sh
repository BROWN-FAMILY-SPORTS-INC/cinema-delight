#!/usr/bin/env bash
# One still of a scene at second <t>, rendered headless, for checking a single frame.
#   tools/still.sh <scene-url> <t> <out.png> [size=1920,1080]
# The scene must freeze at ?t=<seconds> (protocol/contract.md). Headless on purpose: a visible
# window hidden behind others can time its screenshots out.
set -euo pipefail
url="$1"; t="$2"; out="$3"; size="${4:-1920,1080}"
browser="${CHROME:-$(command -v chromium || command -v chromium-browser || command -v google-chrome-stable || command -v google-chrome)}"
sep='?'; [[ "$url" == *\?* ]] && sep='&'
profile="$(mktemp -d)"
trap 'rm -rf "$profile"' EXIT
timeout 60 "$browser" ${CINEMA_BROWSER_FLAGS:-} --headless=new --disable-gpu --disable-dev-shm-usage --hide-scrollbars --no-first-run --user-data-dir="$profile" \
  --window-size="$size" --virtual-time-budget=2500 --screenshot="$out" "${url}${sep}t=${t}" 2>/dev/null
if [[ -s "$out" ]]; then printf '{"ok": true, "wrote": ["%s"], "problems": []}\n' "$out"
else printf '{"ok": false, "wrote": [], "problems": ["no still written"]}\n'; exit 1; fi
