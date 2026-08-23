#!/bin/zsh
# W-53 utility level (b): locality bound via cachegrind on W-47's
# microbench pair F_SS (AoS stock-like records) vs F_PS (typed pool).
# 200 iters/arm, serialized. System valgrind 3.25.1 cachegrind.
set -u
cd /home/m0hawk/Documents/apin/stan/scratch/w47
VG=valgrind
CG=cg_annotate
mkdir -p out/w53
for a in F_SS F_PS; do
  env -u LD_LIBRARY_PATH $VG --tool=cachegrind \
    --cachegrind-out-file=out/w53/cg_$a.out ./bench $a 200 0 \
    > out/w53/cg_$a.run.txt 2>&1
  env -u LD_LIBRARY_PATH $CG out/w53/cg_$a.out > out/w53/cg_$a.ann.txt 2>/dev/null
  echo "done $a"
done
