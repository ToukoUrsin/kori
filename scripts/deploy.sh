#!/usr/bin/env bash
# Deploys the last commit (not the working tree) to Fly, so half-finished edits never go live.
#   scripts/deploy.sh          needs FLY_API_TOKEN in the environment
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d /tmp/kori-deploy.XXXXXX)"
git -C "$repo" archive HEAD | tar -x -C "$tmp"
mkdir -p "$tmp/data"
cp -r "$repo/data/build" "$tmp/data/build"          # built from the dataset, not in git (scripts/fetch_data.sh)
# the demo film (rendered by film/scripts/render.sh, not in git) is served at /film
film="${KORI_FILM:-/bulk2/runs/spankki/film/out/kori.mp4}"
if [ -f "$film" ]; then
  cp "$film" "$tmp/web/public/film.mp4"
  ffmpeg -y -loglevel error -ss "${KORI_FILM_POSTER_AT:-9.4}" -i "$film" -frames:v 1 -vf scale=1280:-2 -q:v 4 "$tmp/web/public/film-poster.jpg"
fi
cd "$tmp"
fly deploy -a kori-coach --ha=false --now
echo "deployed $(git -C "$repo" rev-parse --short HEAD)"
