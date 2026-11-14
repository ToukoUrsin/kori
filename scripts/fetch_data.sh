#!/usr/bin/env bash
# Download S-Pankki's synthetic Junction 2026 dataset and build the files Kori reads.
# The dataset itself is not part of this repository.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/dataset"
OUT="$ROOT/data/build"
mkdir -p "$OUT"
if [ ! -f "$SRC/tx_junction_transactions.csv" ]; then
  git clone --depth 1 https://github.com/hackjunction/Junction-2026-S-pankki "$SRC"
fi
cd "$ROOT/backend"
uv sync
uv run python -I "$ROOT/scripts/to_parquet.py" "$SRC" "$OUT"          # CSV -> Parquet (3.6M transactions, 5,100 customers)
PYTHONPATH=. uv run python scripts/build_peers.py                       # per-customer monthly medians for peer groups
echo "Done. Statistics Finland benchmarks are already in data/benchmarks (rebuild: python scripts/fetch_benchmarks.py)."
