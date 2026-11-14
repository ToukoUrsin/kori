#!/usr/bin/env bash
# Renders the film in a container (Chrome needs a quiet network of its own, see capture/run.sh), then masters the
# sound to -16 LUFS integrated, under -1 dBTP: measured, then one linear gain and a peak limiter (the picture is copied).
#   scripts/render.sh <name> [composition]         -> /bulk2/runs/spankki/film/out/<name>.mp4 (+ <name>.raw.mp4)
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
out=/bulk2/runs/spankki/film
name=${1:?name}; comp=${2:-Film}
raw="$out/out/$name.raw.mp4"; final="$out/out/$name.mp4"
mkdir -p "$out/out"
docker image inspect kori-capture >/dev/null 2>&1 || docker build -q -t kori-capture "$here/capture"
docker run --rm --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$here:$here" -v "$out:$out" -w "$here" kori-capture \
  npx remotion render src/index.ts "$comp" "$raw" --concurrency=16 --crf=18 --log=error 2>&1 | grep -v "webpack.cache" || true

# pass 1: measure the integrated loudness of the raw mix
I=$(ffmpeg -hide_banner -nostats -i "$raw" -af ebur128 -f null - 2>&1 | grep -E "^ +I:" | tail -1 | awk '{print $2}')
gain=$(python3 -c "print(round(-16 - ($I), 2))")
# pass 2: one linear gain to -16 LUFS; a brick-wall limiter at -2 dBFS catches the few peaks the gain pushes over,
# so true peak stays under -1 dBTP (loudnorm itself falls back to dynamic gain riding when peaks are in the way)
echo "raw $I LUFS, gain $gain dB"
ffmpeg -hide_banner -loglevel error -y -i "$raw" -c:v copy \
  -af "volume=${gain}dB,alimiter=limit=0.794:attack=1:release=60:level=false,aresample=48000" \
  -c:a aac -b:a 256k -movflags +faststart "$final"
ffmpeg -hide_banner -nostats -i "$final" -af ebur128=peak=true -f null - 2>&1 | grep -A12 "^\[Parsed_ebur128.*Summary" | grep -E "I:|LRA:|Peak:" || true
ls -la "$final"
