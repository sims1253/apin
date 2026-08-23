#!/bin/bash
# W-40: build one patched-stdlib kronecker_gp .so via bridgestan (copied .stan)
# usage: build_so.sh <variant-name> "<make_args python list>"
set -e
ROOT=/home/m0hawk/Documents/apin/stan
V=$1; MARGS=$2
D=$ROOT/scratch/w40/builds/${V}
mkdir -p "$D"
if [ -f "$D/kronecker_gp_model.so" ]; then echo "[w40] $V: cached"; exit 0; fi
cp $ROOT/models/kronecker_gp.stan "$D/kronecker_gp.stan"
cd $ROOT
env -u LD_LIBRARY_PATH BRIDGESTAN=$HOME/.bridgestan/bridgestan-2.9.0 MAKEFLAGS=-j2 \
  uv run python -c "
import bridgestan
so = bridgestan.compile_model('scratch/w40/builds/${V}/kronecker_gp.stan',
      make_args=${MARGS})
print('built', so)
"
