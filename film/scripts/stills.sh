#!/usr/bin/env bash
# Stills of the film at the given frames, and one contact sheet of them. Runs in the container, like the render
# (the host's Chrome hangs on a busy machine).
#   scripts/stills.sh <name> <frame> [frame ...]
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
name=$1; shift
out=/bulk2/runs/spankki/film/stills/$name
mkdir -p "$out"
docker run --rm --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$here:$here" -v /bulk2/runs/spankki/film:/bulk2/runs/spankki/film -w "$here" kori-capture \
  node scripts/stills.mjs "$out" "$@"
n=$#
ffmpeg -y -loglevel error -pattern_type glob -i "$out/*.png" -vf "scale=640:-1,tile=3x$(( (n + 2) / 3 ))" -frames:v 1 "$out/sheet.jpg"
echo "$out/sheet.jpg"
