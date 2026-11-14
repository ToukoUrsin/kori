#!/usr/bin/env bash
# Stills of the film at the given frames, and one contact sheet of them.
#   scripts/stills.sh <name> <frame> [frame ...]
set -euo pipefail
cd "$(dirname "$0")/.."
name=$1; shift
out=/bulk2/runs/spankki/film/stills/$name
mkdir -p "$out"
i=0
for f in "$@"; do
	npx remotion still src/index.ts Film "$out/$(printf %02d $i)-$f.png" --frame="$f" --log=error >/dev/null &
	i=$((i+1))
	if (( i % 6 == 0 )); then wait; fi
done
wait
ffmpeg -y -loglevel error -pattern_type glob -i "$out/*.png" -vf "scale=640:-1,tile=3x$(( (i + 2) / 3 ))" -frames:v 1 "$out/sheet.jpg"
echo "$out/sheet.jpg"
