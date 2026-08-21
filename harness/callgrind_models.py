#!/usr/bin/env python
"""Phase 1: callgrind inclusive-cost attribution on sampling binaries.

Short runs (default 40 warmup + 40 draws, 1 chain) under valgrind --tool=callgrind.
Produces callgrind.out.<pid> + callgrind_annotate text; parsed into
results/profile/<model>.callgrind.json with top functions and named-bucket shares:
model log_prob (model_base::log_prob), autodiff (var/chain/reverse), Eigen/memcpy,
checks (check_*), everything else.
"""
import json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'results/profile'; OUT.mkdir(parents=True, exist_ok=True)
WARMUP, DRAWS = 40, 40
SEED = 20260819

BUCKETS = [
    ('model_log_prob', r'log_prob|_lpdf'),
    ('autodiff_reverse', r'(chain|reverse|adjoint|arena|recover_memory|set_zero_adjoint)'),
    ('checks', r'(check_|validate|throw_)'),
    ('eigen_linalg', r'(Eigen|LLT|cholesky|gemm|gemv|Eigen::internal)'),
    ('memcpy_alloc', r'(memcpy|memmove|operator new|_Znwm|malloc|free)'),
    ('rng', r'(boost::random|base_rng|uniform_|normal_rng)'),
    ('io', r'(std::|ostream|fstream|csv)'),
]

def run_one(model, warmup=WARMUP, draws=DRAWS):
    exe = ROOT / 'build' / f'{model}__default' / 'model'
    od = OUT / model; od.mkdir(exist_ok=True)
    cg = od / f'callgrind.out'; ann = od / 'callgrind_annotate.txt'
    if not ann.exists():
        cmd = ['valgrind', '--tool=callgrind', '--simulate-cache=yes',
               f'--callgrind-out-file={cg}',
               str(exe), 'id=1', 'data', f'file={ROOT}/data/{model}.json',
               'random', f'seed={SEED}', 'output', f'file={od}/chain.csv',
               'method=sample', f'num_warmup={warmup}', f'num_samples={draws}', 'save_warmup=0']
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-300:])
        subprocess.run(['callgrind_annotate', str(cg)], stdout=open(ann, 'w'), check=False)
    txt = ann.read_text()

    import re as _re
    # 9 event columns; each: number-or-dot, optional (x%); then file:function
    LINE9 = _re.compile(r'^\s*([\d,]+)(?:\s+\(\s*[\d.,]+%\s*\))?'
                        r'(?:\s+(?:[\d,]+|\.)(?:\s+\(\s*[\d.,]+%\s*\))?){8}'
                        r'\s+(\S.*)$')
    def parse_line(line):
        m = LINE9.match(line)
        if not m: return None
        name = m.group(2).strip()
        if ':' not in name: return None
        return int(m.group(1).replace(',', '')), name

    total = None
    funcs = []
    cache = dict(Ir=0, Dr=0, Dw=0, I1mr=0, D1mr=0, D1mw=0, ILmr=0, DLmr=0, DLmw=0)
    for line in txt.splitlines():
        m = _re.match(r'\s*([\d,]+)\s+\(100\.0%\).*PROGRAM TOTALS', line)
        if m and ' ' in line and 'Dr' not in line:
            # PROGRAM TOTALS line: 9 columns as N (100.0%)
            nums = [int(x.replace(',', '')) for x in _re.findall(r'([\d,]+)\s+\(', line)]
            if len(nums) >= 9:
                total = nums[0]
                for k, v in zip(['Ir','Dr','Dw','I1mr','D1mr','D1mw','ILmr','DLmr','DLmw'], nums[:9]):
                    cache[k] = v
            continue
        pr = parse_line(line)
        if pr:
            funcs.append(pr)
    if total is None:
        totals_line = next((l for l in txt.splitlines() if 'PROGRAM TOTALS' in l), '')
        nums = [int(x.replace(',', '')) for x in _re.findall(r'([\d,]+)\s+\(', totals_line)]
        total = nums[0] if nums else 0
        for k, v in zip(['Ir','Dr','Dw','I1mr','D1mr','D1mw','ILmr','DLmr','DLmw'], nums[:9]):
            cache[k] = v

    ONE_TIME = _re.compile(r'(rapidjson|json_data|istream|filebuf|xsgetn|basic_string|sentry)')
    buckets = {name: 0 for name, _ in BUCKETS}
    one_time_cost = 0
    leftovers = []
    for cost, fname in funcs:
        if ONE_TIME.search(fname):
            one_time_cost += cost
            continue
        for name, pat in BUCKETS:
            if _re.search(pat, fname):
                buckets[name] += cost
                break
        else:
            leftovers.append((fname, cost))
    steady_total = total - one_time_cost if total else 0
    out = dict(model=model, iters=f'{warmup}+{draws}',
               total_instructions=total, one_time_io_instructions=one_time_cost,
               steady_state_instructions=steady_total,
               cache_totals=cache,
               d1_mr=round(cache['D1mr'] / cache['Dr'], 4) if cache.get('Dr') else None,
               dl_mr=round(cache['DLmr'] / cache['Dr'], 4) if cache.get('Dr') else None,
               buckets=buckets,
               bucket_share={k: round(v / steady_total, 4) for k, v in buckets.items() if steady_total},
               top_funcs=[(f, c, round(c / total, 4)) for c, f in funcs[:25]] if total else [],
               top_leftover=[(f, c) for f, c in sorted(leftovers, key=lambda x: -x[1])[:10]])
    (od / 'callgrind.json').write_text(json.dumps(out, indent=2))
    return out

if __name__ == '__main__':
    models = sys.argv[1].split(',') if len(sys.argv) > 1 else ['diamonds', 'radon_partially_pooled_noncentered', 'accel_gp', 'pilots', 'lsat_model']
    for m in models:
        try:
            r = run_one(m)
            print(f"[callgrind] {m}: total={r['total_instructions']:,} "
                  + ' '.join(f"{k}={v:.1%}" for k, v in r['bucket_share'].items()), flush=True)
        except Exception as e:
            print(f'[callgrind] {m}: FAILED {e}', flush=True)
