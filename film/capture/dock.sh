#!/usr/bin/env bash
# Runs a command in the kori-capture container with the film folder and /bulk3/runs/spankki/film2 mounted.
#   capture/dock.sh node capture/record.mjs <scenario> --out /bulk3/runs/spankki/film2/cap/<scenario>
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
out=/bulk3/runs/spankki/film2
mkdir -p "$out"
exec docker run --rm --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp -e ELEVENLABS_API_KEY \
  -v "$here:$here" -v "$out:$out" -v /bulk3/runs/opens/final/kori:/bulk3/runs/opens/final/kori:ro -w "$here" kori-capture "$@"
