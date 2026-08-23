#!/bin/bash
# W-40: compile a unit driver against STOCK semantics while the live tree is
# patched: pristine copies of the two patched headers shadow them via -I order.
set -e
BS=$HOME/.bridgestan/bridgestan-2.9.0
M=$BS/stan/lib/stan_math
cd /home/m0hawk/Documents/apin/stan/scratch/w40
env -u LD_LIBRARY_PATH g++ -std=c++17 -O2 $3 -pthread -D_REENTRANT \
  -I /home/m0hawk/Documents/apin/stan/scratch/w40/pristine_override \
  -I $BS/stan/src -I $BS/stan/lib/rapidjson_1.1.0 \
  -I $M -I $M/lib/eigen_3.4.0 -I $M/lib/boost_1.87.0 \
  -I $M/lib/sundials_6.1.1/include -I $M/lib/sundials_6.1.1/src/sundials \
  -I $M/lib/tbb_2020.3/include \
  -x c++ "$1" -o "$2" \
  -L $M/lib/tbb -Wl,-rpath,$M/lib/tbb -ltbb
