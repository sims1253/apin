#!/usr/bin/env bash
# Phase 1 driver: microbench compile+run, Stan profile() runs, callgrind attribution.
# Strictly sequential; <=4 cores at all times.
set -uo pipefail
cd "$(dirname "$0")/.."
export MAKEFLAGS="-j4" OMP_NUM_THREADS=1 STAN_NUM_THREADS=1
MATH=placeholder

echo "=== [P1-1] compile microbenches ==="
CXX="g++ -std=c++17 -O3 -D_REENTRANT -march=native -I$HOME/.cmdstan/cmdstan-2.39.0/stan/lib/stan_math -I$HOME/.cmdstan/cmdstan-2.39.0/stan/lib/stan_math/lib/eigen_3.4.0 -I$HOME/.cmdstan/cmdstan-2.39.0/stan/lib/stan_math/lib/boost_1.87.0 -I$HOME/.cmdstan/cmdstan-2.39.0/stan/lib/stan_math/lib/sundials_6.1.1/include -I$HOME/.cmdstan/cmdstan-2.39.0/stan/lib/stan_math/lib/tbb_2020.3/include"
$CXX bench/bench_lpdf.cpp -o bench/bench_lpdf 2> bench/bench_lpdf.err && echo "bench_lpdf built" || tail -5 bench/bench_lpdf.err
$CXX bench/bench_var_alloc.cpp -o bench/bench_var_alloc 2> bench/bench_var_alloc.err && echo "bench_var_alloc built" || tail -5 bench/bench_var_alloc.err
$CXX bench/bench_ps_point.cpp -o bench/bench_ps_point 2> bench/bench_ps_point.err && echo "bench_ps_point built" || tail -5 bench/bench_ps_point.err
$CXX -O2 bench/bench_cache.cpp -o bench/bench_cache 2> bench/bench_cache.err && echo "bench_cache built" || tail -5 bench/bench_cache.err

echo "=== [P1-2] run microbenches ==="
for b in bench_lpdf bench_var_alloc bench_ps_point bench_cache; do
  [ -x bench/$b ] && { echo "--- $b"; ./bench/$b | tee bench/$b.out 2>/dev/null; }
done

echo "=== [P1-3] Stan profile() runs (models_prof) ==="
uv run python harness/profile_models.py

echo "=== [P1-4] callgrind attribution ==="
uv run python harness/callgrind_models.py

echo "PHASE1 RUNS DONE"
