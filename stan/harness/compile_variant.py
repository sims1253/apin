#!/usr/bin/env python
"""Direct stanc+make compile of a model variant. Bypasses cmdstanpy option handling.

variant spec: name:stanc_args|cxxflags   (empty parts allowed)
"""
import json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CMDSTAN = Path.home() / '.cmdstan/cmdstan-2.39.0'
MANIFEST = json.loads((ROOT/'harness/core_manifest.json').read_text())

VARIANTS = {
    'default': dict(stanc=[], cxx=''),
    'oexp': dict(stanc=['--Oexperimental'], cxx=''),
    'march_native': dict(stanc=[], cxx='-march=native -O3 -mtune=native'),  # QUARANTINED: gcc 11.4 memory corruption
    'clang_native': dict(stanc=[], cxx='-march=native -O3', cxx_override='clang++', no_pch=True),
    'oexp_march_native': dict(stanc=['--Oexperimental'], cxx='-march=native -O3 -mtune=native'),
}

def compile_variant(model, variant):
    v = VARIANTS[variant]
    bdir = ROOT/'build'/f'{model}__{variant}'
    exe = bdir/'model'
    if exe.exists():
        return 0.0
    bdir.mkdir(parents=True, exist_ok=True)
    stan_src = ROOT/f'models/{model}.stan'
    hpp = bdir/'model.hpp'
    t0 = time.time()
    r = subprocess.run([str(CMDSTAN/'bin/stanc'), '--o', str(hpp)] + v['stanc'] + [str(stan_src)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'stanc failed: {r.stderr[:400]}')
    target = bdir/'model'   # make target must be an absolute path under cmdstan tree? use relative path trick
    # run make from cmdstan dir with absolute target path
    make_cmd = ['make', str(target)]
    env = dict(os.environ)
    env['MAKEFLAGS'] = '-j4'
    env['CXXFLAGS'] = (v['cxx'] + ' ' + env.get('CXXFLAGS', '')) if v['cxx'] else env.get('CXXFLAGS', '')
    if v.get('cxx_override'):
        env['CXX'] = v['cxx_override']
    if v.get('no_pch'):
        env['PRECOMPILED_HEADERS'] = 'false'
    r2 = subprocess.run(make_cmd, cwd=str(CMDSTAN), capture_output=True, text=True, env=env)
    if r2.returncode != 0 or not exe.exists():
        raise RuntimeError(f'make failed: {r2.stdout[-400:]} {r2.stderr[-400:]}')
    return time.time() - t0

if __name__ == '__main__':
    models = [e['model'] for e in MANIFEST]
    if len(sys.argv) > 1:
        variants = sys.argv[1].split(',')
        models = models if len(sys.argv) < 3 else sys.argv[2].split(',')
    else:
        variants = ['oexp']
    for variant in variants:
        for m in models:
            try:
                s = compile_variant(m, variant)
                print(f'[compile] {m}/{variant}: {"cached" if s == 0 else f"{s:.1f}s"}', flush=True)
            except Exception as e:
                print(f'[compile] {m}/{variant}: FAILED {e}', flush=True)
