#!/usr/bin/env python
"""Phase 1: Stan-level profiling of models_prof/ copies.

For each profiled model: run 1 chain, 200 warmup + 200 draws (short but with
full windowed adaptation), collect profile_file= CSV. Profile CSV columns
(2.39): thread_id,total_time,forward_time,reverse_time,...,name-ish tail.
Outputs results/profile/<model>.json with per-block forward/reverse/total and
share of total sampler wall.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CMDSTAN = Path.home() / '.cmdstan/cmdstan-2.39.0'
PROF = ROOT / 'models_prof'
OUT = ROOT / 'results/profile'; OUT.mkdir(parents=True, exist_ok=True)
WARMUP, DRAWS = 200, 200
SEED = 20260819

def compile_prof(model):
    exe = ROOT / 'build' / f'{model}__prof' / 'model'
    if exe.exists():
        return exe
    bdir = exe.parent; bdir.mkdir(parents=True, exist_ok=True)
    (bdir / 'model.stan').write_text((PROF / f'{model}.stan').read_text())
    r = subprocess.run([str(CMDSTAN / 'bin/stanc'), '--o', str(bdir / 'model.hpp'), str(bdir / 'model.stan')],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    r2 = subprocess.run(['make', str(exe)], cwd=str(CMDSTAN),
                        capture_output=True, text=True, env={**os.environ, 'MAKEFLAGS': '-j4'})
    if r2.returncode != 0 or not exe.exists():
        raise RuntimeError(r2.stderr[-300:])
    return exe

def run_profiled(model):
    exe = compile_prof(model)
    od = OUT / model; od.mkdir(exist_ok=True)
    csv_path = od / 'chain.csv'; prof_path = od / 'profile.csv'
    if csv_path.exists() and prof_path.exists():
        wall = None
    else:
        cmd = [str(exe), 'id=1', 'data', f'file={ROOT}/data/{model}.json',
               'random', f'seed={SEED}', 'output', f'file={csv_path}',
               f'profile_file={prof_path}', 'method=sample',
               f'num_warmup={WARMUP}', f'num_samples={DRAWS}', 'save_warmup=0']
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        wall = time.time() - t0
        if r.returncode != 0:
            raise RuntimeError(r.stderr[:300])
    # parse elapsed from chain csv
    txt = csv_path.read_text().splitlines()
    warm = samp = None
    for i, line in enumerate(txt):
        m = re.search(r'Elapsed Time: ([\d.eE+-]+) seconds \(Warm-up\)', line)
        if m: warm = float(m.group(1))
        m2 = re.match(r'#\s*([\d.eE+-]+) seconds \(Sampling\)', line) if warm is not None else None
        if m2 and samp is None: samp = float(m2.group(1))
    # parse profile csv
    plines = [l for l in prof_path.read_text().splitlines() if l.strip()]
    hdr = plines[0].split(',')
    prows = [dict(zip(hdr, l.split(','))) for l in plines[1:]]
    blocks = {}
    for row in prows:
        name = row.get('name', row.get('profile_name', '?'))
        blocks[name] = {k: float(v) for k, v in row.items()
                        if k not in ('name', 'profile_name', 'thread_id') and v not in ('', 'NA')}
    total_samp = (warm or 0) + (samp or 0)
    out = dict(model=model, wall_s=wall, warmup_s=warm, sampling_s=samp,
               total_sampler_s=total_samp, profile_blocks=blocks,
               profile_total_s=sum(b.get('total_time', 0) for b in blocks.values()))
    (od / 'summary.json').write_text(json.dumps(out, indent=2))
    return out

if __name__ == '__main__':
    models = sys.argv[1].split(',') if len(sys.argv) > 1 else \
        [f.stem for f in sorted(PROF.glob('*.stan'))]
    for m in models:
        try:
            r = run_profiled(m)
            print(f"[profile] {m}: sampler={r['total_sampler_s']:.2f}s "
                  f"profiled={r['profile_total_s']:.2f}s "
                  + ' '.join(f"{k}={v['total_time']:.2f}s" for k, v in r['profile_blocks'].items()),
                  flush=True)
        except Exception as e:
            print(f'[profile] {m}: FAILED {e}', flush=True)
