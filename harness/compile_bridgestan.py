#!/usr/bin/env python
"""Compile CORE_SET models to BridgeStan .so (Stan 2.39.0 via bridgestan 2.9.0)."""
import json, os, sys
from pathlib import Path
os.environ['BRIDGESTAN'] = str(Path.home()/'.bridgestan/bridgestan-2.9.0')
os.environ['MAKEFLAGS'] = '-j4'
import bridgestan

ROOT = Path(__file__).resolve().parent.parent
manifest = json.loads((ROOT/'harness/core_manifest.json').read_text())
out_dir = ROOT/'bs_models'; out_dir.mkdir(exist_ok=True)
for e in manifest:
    m = e['model']
    so = out_dir/f'model_{m}.so'
    if so.exists():
        print(f'[bs] {m}: cached', flush=True); continue
    try:
        path = bridgestan.compile_model(str(ROOT/f'models/{m}.stan'))
        import shutil
        shutil.copy(path, so)
        print(f'[bs] {m}: OK', flush=True)
    except Exception as ex:
        print(f'[bs] {m}: FAILED {str(ex)[:200]}', flush=True)
