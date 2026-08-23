#!/bin/bash
# W-53 gate (b): full sampler draws md5, stock vs patched hier_2pl .so.
# W-29 protocol verbatim: warmup 100, samples 50, seed 20260819, pf init,
# --metric-window 50. Binary: walnutpie build_w36exp (READ-ONLY, never rebuilt).
set -u
ROOT=/home/m0hawk/Documents/apin/stan
CLI=$ROOT/external/walnutpie/build_w36exp/examples/stan_cli
OUT=$ROOT/scratch/w53/draws
mkdir -p $OUT
run() {  # run <arm>
  env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 $CLI \
    $ROOT/scratch/w53/model_hier_2pl_$1/hier_2pl_model.so \
    $ROOT/data/hier_2pl.json \
    --seed 20260819 --init-file $ROOT/inits_w25/hier_2pl/rep0/chain_0.txt \
    --warmup 100 --samples 50 --metric-window 50 \
    --output $OUT/draws_$1.csv > $OUT/cli_$1.log 2>&1
  echo "$1 rc=$?"
}
[ -f $OUT/draws_stock.csv ] || run stock
[ -f $OUT/draws_patched.csv ] || run patched
md5sum $OUT/draws_stock.csv $OUT/draws_patched.csv
if cmp -s $OUT/draws_stock.csv $OUT/draws_patched.csv; then
  echo "DRAWS MD5-IDENTICAL: PASS"
else
  echo "DRAWS DIFFER: FAIL"
fi
