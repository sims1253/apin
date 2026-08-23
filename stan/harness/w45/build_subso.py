#!/usr/bin/env python
"""W-45: build subsample .so per (model, alpha) via bridgestan 2.9.0.

Copies the .stan into scratch/w45/build_<model>_a<alpha>/ (W-27 cache
gotcha: compile_model caches <stem>_model.so next to the .stan), then
compiles with DEFAULT flags + STAN_THREADS=1 (like bs_models_threads).
lsat_model uses the data-block-modified copy (parameters unchanged).
Serialized builds (-j2 inside make); env -u LD_LIBRARY_PATH.
"""
import os, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ['BRIDGESTAN'] = str(Path.home() / '.bridgestan/bridgestan-2.9.0')
os.environ['MAKEFLAGS'] = '-j2'
import bridgestan  # noqa: E402

MODELS = ['hier_2pl', 'blr', 'lsat_model', 'arma11']
ALPHAS = [25, 10]
OUT = ROOT / 'scratch' / 'w45'


def main():
    only = sys.argv[1:] or None
    for m in MODELS:
        for a in ALPHAS:
            tag = f'{m}_a{a}'
            if only and tag not in only:
                continue
            bdir = OUT / f'build_{tag}'
            bdir.mkdir(parents=True, exist_ok=True)
            src = (OUT / 'data' / 'lsat_model_sub.stan' if m == 'lsat_model'
                   else ROOT / 'models' / f'{m}.stan')
            dst = bdir / f'{m}.stan'
            shutil.copy(src, dst)
            so = bdir / f'{m}_model.so'
            if so.exists():
                print(f'[w45] {tag}: cached', flush=True)
                continue
            path = bridgestan.compile_model(str(dst),
                                            make_args=['STAN_THREADS=1'])
            assert Path(path) == so, f'{path} != {so}'
            print(f'[w45] {tag}: OK -> {so.name}', flush=True)


if __name__ == '__main__':
    main()
