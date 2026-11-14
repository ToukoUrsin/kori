#!/usr/bin/env bash
# Renders the film in a container (Chrome needs a quiet network of its own, see capture/run.sh).
#   scripts/render.sh <name> [composition]         -> /bulk2/runs/spankki/film/out/<name>.mp4
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
out=/bulk2/runs/spankki/film
name=${1:?name}; comp=${2:-Film}
mkdir -p "$out/out"
docker image inspect kori-capture >/dev/null 2>&1 || docker build -q -t kori-capture "$here/capture"
docker run --rm --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$here:$here" -v "$out:$out" -w "$here" kori-capture \
  npx remotion render src/index.ts "$comp" "$out/out/$name.mp4" --concurrency=16 --crf=18 --log=error 2>&1 | grep -v "webpack.cache" || true
ls -la "$out/out/$name.mp4"
