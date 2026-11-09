#!/usr/bin/env bash
# Build a bare image from the committed tree (git archive, so nothing untracked gets in) and run every check in it.
#   tests/clean/run.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
ctx="$(mktemp -d)"; trap 'rm -rf "$ctx"' EXIT
git archive HEAD | tar -x -C "$ctx"
docker build -q -t cinema-delight-clean -f "$ctx/tests/clean/Dockerfile" "$ctx" >/dev/null
docker run --rm cinema-delight-clean
