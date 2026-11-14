#!/usr/bin/env bash
# Runs the recorder in a container, so Chrome has a network of its own.
# (On a busy build machine other containers come and go, Chrome sees every one as a "network change" and drops
# its open requests. A phone does not have that problem; a recording should not either.)
#
#   capture/run.sh <scenario> [--base URL] [--out DIR]        needs ELEVENLABS_API_KEY in the environment
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
out=/bulk2/runs/spankki/film
mkdir -p "$out"
docker image inspect kori-capture >/dev/null 2>&1 || docker build -q -t kori-capture "$here/capture"
exec docker run --rm --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp -e ELEVENLABS_API_KEY \
  -v "$here:$here" -v "$out:$out" -w "$here" kori-capture node capture/record.mjs "$@"
