#!/bin/bash
# W-35: build one kronecker_gp variant .so via bridgestan (copied .stan per variant)
# usage: build_variant.sh <variant-name> "<extra CXXFLAGS>"
set -e
ROOT=/home/m0hawk/Documents/apin/stan
V=$1; FLAGS=$2
D=$ROOT/scratch/w35/${V}_build
mkdir -p "$D"
if [ -f "$D/kronecker_gp_model.so" ]; then echo "[w35] $V: cached"; exit 0; fi
cp $ROOT/models/kronecker_gp.stan "$D/kronecker_gp.stan"
cd $ROOT
env -u LD_LIBRARY_PATH BRIDGESTAN=$HOME/.bridgestan/bridgestan-2.9.0 MAKEFLAGS=-j2 \
  uv run python -c "
import bridgestan, sys
so = bridgestan.compile_model('scratch/w35/${V}_build/kronecker_gp.stan',
      make_args=['CXXFLAGS=${FLAGS}'] if '${FLAGS}' else [])
print('built', so)
"
