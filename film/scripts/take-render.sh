#!/usr/bin/env bash
# The film cut around the founder's voice take, in one command:
#   scripts/take-render.sh                 -> /bulk3/runs/spankki/film2/out/kori-film.mp4
# Reads the cold open and the end card from /bulk3/runs/opens/final/kori/ as they are now (so a new open is one
# re-run), brings the recordings in (scripts/take-import.mjs), renders the composition "Take" in the container
# (Chrome only works there), then masters the sound: measured, one linear gain to -16 LUFS, a peak limiter under
# -1 dBTP; the picture is copied.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
run=${KORI_TAKE:-/bulk3/runs/spankki/film2}
name=${1:-kori-film}
raw="$run/work/$name.raw.mp4"; final="$run/out/$name.mp4"
mkdir -p "$run/out" "$run/work"
cd "$here"
node scripts/take-plan.mjs >/dev/null
node scripts/take-import.mjs
docker run --rm --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$here:$here" -v "$run:$run" -w "$here" kori-capture \
  npx remotion render src/index.ts Take "$raw" --public-dir "$run/public" --concurrency="${KORI_JOBS:-8}" --crf=17 --log=error 2>&1 | grep -v "webpack.cache" || true
test -s "$raw"
I=$(ffmpeg -hide_banner -nostats -i "$raw" -af ebur128 -f null - 2>&1 | grep -E "^ +I:" | tail -1 | awk '{print $2}')
gain=$(python3 -c "print(round(-16 - ($I), 2))")
echo "raw $I LUFS, gain $gain dB"
ffmpeg -hide_banner -loglevel error -y -i "$raw" -c:v copy \
  -af "volume=${gain}dB,alimiter=limit=0.794:attack=1:release=60:level=false,aresample=48000" \
  -c:a aac -b:a 256k -movflags +faststart "$final.tmp.mp4"
mv "$final.tmp.mp4" "$final"
ffmpeg -hide_banner -nostats -i "$final" -af ebur128=peak=true -f null - 2>&1 | grep -A12 "Summary" | grep -E "I:|LRA:|Peak:" || true
ffprobe -v error -show_entries format=duration -of csv=p=0 "$final"
ls -la "$final"
