#!/usr/bin/env bash
# nindan: one command to rerun the whole Phase 0 grid + analysis.
# Resource policy: <=4 single-threaded processes at all times.
set -euo pipefail
cd "$(dirname "$0")/.."
export MAKEFLAGS="-j4" OMP_NUM_THREADS=1 STAN_NUM_THREADS=1

echo "=== [1/6] compile cmdstan variants (default, oexp) ==="
uv run python harness/compile_variant.py default
uv run python harness/compile_variant.py oexp || true   # 2.39 --Oexperimental fails on 3 models (known)

echo "=== [2/6] cmdstan grid (default + oexp x 3 reps) ==="
uv run python harness/run_grid.py --variants default,oexp --reps 3

echo "=== [3/6] nutpie grid ==="
uv run python harness/run_nutpie.py --reps 3

echo "=== [3b/6] walnutpie grid ==="
uv run python harness/compile_bridgestan.py
uv run python harness/run_walnutpie.py --reps 3

echo "=== [4/6] ESS (R posterior) ==="
uv run python harness/compute_ess.py

echo "=== [5/6] aggregate tables ==="
uv run python harness/aggregate.py

echo "=== [6/6] phase1 atlas refresh ==="
uv run python harness/atlas.py || true

echo "=== [7/7] refresh dashboard ==="
python3 harness/make_dashboard.py

echo "ALL DONE — see results/"
