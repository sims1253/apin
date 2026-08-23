#!/bin/zsh
# W-53 measurement: callgrind Ir/grad, stock vs patched hier_2pl .so.
# W-29 protocol verbatim (warmup 100 samples 50, seed 20260819, pf init,
# --metric-window 50), valgrind 3.23 (~/vginstall) for era-consistency
# with W-29/W-34/W-47 numbers. One job at a time.
set -u
ROOT=/home/m0hawk/Documents/apin/stan
CLI=$ROOT/external/walnutpie/build_w36exp/examples/stan_cli
VG=$HOME/vginstall/bin/valgrind
CA=$HOME/vginstall/bin/callgrind_annotate
OUT=$ROOT/scratch/w53/profile
mkdir -p $OUT
for arm in stock patched; do
  od=$OUT/$arm; mkdir -p $od
  cg=$od/callgrind.out
  if [ ! -f $cg ]; then
    env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 $VG --tool=callgrind \
      --callgrind-out-file=$cg $CLI \
      $ROOT/scratch/w53/model_hier_2pl_$arm/hier_2pl_model.so \
      $ROOT/data/hier_2pl.json \
      --seed 20260819 --init-file $ROOT/inits_w25/hier_2pl/rep0/chain_0.txt \
      --warmup 100 --samples 50 --metric-window 50 \
      --output $od/draws.csv > $od/cli.log 2>&1
    echo "done callgrind $arm rc=$?"
  fi
  for flag in "" "--inclusive=yes"; do
    name=${flag:+incl_}ann.txt
    [ -f $od/$name ] && [ -s $od/$name ] || \
      env -u LD_LIBRARY_PATH $CA $flag $cg > $od/$name 2>/dev/null
  done
done
