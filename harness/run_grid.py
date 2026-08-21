#!/usr/bin/env python
"""nindan benchmark runner - Phase 0 harness.

Runs the CORE_SET grid with checkpointing:
  variants: default, oexp (nutpie handled by run_nutpie.py)
  4 chains x (1000 warmup + 1000 draws), 1 thread/chain, <=4 concurrent processes.

Resource discipline: MAKEFLAGS=-j4 for compiles; sampling runs 4 single-threaded
chains in parallel; nothing else concurrent.
"""
import argparse, csv, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / 'harness/core_manifest.json').read_text())
CMDSTAN = Path.home() / '.cmdstan/cmdstan-2.39.0'
RUNS = ROOT / 'runs'; RESULTS = ROOT / 'results'; LOGS = ROOT / 'logs'
for d in (RUNS, RESULTS, LOGS): d.mkdir(exist_ok=True)

WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
MAX_DEPTH = 10  # cmdstan default

VARIANTS = {
    'default': dict(stanc_opts=[]),
    'oexp':    dict(stanc_opts=['--Oexperimental']),
    # Phase 2c will add 'march_native' with custom CXXFLAGS
}


def set_env():
    os.environ['MAKEFLAGS'] = '-j4'
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['STAN_NUM_THREADS'] = '1'


def elapsed_from_csv(path):
    """Parse Elapsed Time comments + sampler diagnostics from a CmdStan CSV."""
    txt = path.read_text().splitlines()
    warm = samp = None
    for i, line in enumerate(txt):
        # format A: one line, format B: two lines (leading '#' then continuation)
        m = re.match(r'#\s*Elapsed Time: ([\d.eE+-]+) seconds \(Warm-up\), ([\d.eE+-]+) seconds \(Sampling\)', line)
        if m:
            warm, samp = float(m.group(1)), float(m.group(2))
        elif re.search(r'Elapsed Time:.*\(Warm-up\)', line) and i + 1 < len(txt):
            m2 = re.match(r'#\s*([\d.eE+-]+) seconds \(Sampling\)', txt[i + 1])
            m1 = re.search(r'Elapsed Time: ([\d.eE+-]+) seconds \(Warm-up\)', line)
            if m1 and m2:
                warm, samp = float(m1.group(1)), float(m2.group(1))
    hdr_idx = next(i for i, l in enumerate(txt) if l and not l.startswith('#') and ',' in l)
    header = txt[hdr_idx].split(',')
    rows = [l.split(',') for l in txt[hdr_idx + 1:] if l and not l.startswith('#') and ',' in l]

    def col(name):
        if name not in header:
            return []
        j = header.index(name)
        out = []
        for r in rows:
            if len(r) == len(header):
                try:
                    out.append(float(r[j]))
                except ValueError:
                    pass
        return out

    leap = col('n_leapfrog__')
    div = col('divergent__')
    td = col('treedepth__')
    acc = col('accept_stat__')
    step = col('stepsize__')
    lp = col('lp__')
    return dict(
        warmup_s=warm, sampling_s=samp, n_draws=len(rows),
        n_leapfrog_total=int(sum(leap)),
        n_leapfrog_sampling=int(sum(leap[len(leap) // 2:])) if leap else 0,
        divergences=int(sum(1 for v in div if v == 1)),
        treedepth_hits=int(sum(1 for v in td if v >= MAX_DEPTH)),
        stepsize_final=step[-1] if step else None,
        accept_mean=sum(acc) / len(acc) if acc else None,
        lp_mean=sum(lp) / len(lp) if lp else None,
    )


def compile_model(model, variant):
    """Compile via harness/compile_variant.py (direct stanc + make; cmdstanpy mangles
    list stanc_options and built mislabeled default exes - do not use it here)."""
    sys.path.insert(0, str(ROOT / 'harness'))
    from compile_variant import compile_variant
    return ROOT / 'build' / f'{model}__{variant}' / 'model', compile_variant(model, variant)


def run_config(model, variant, rep):
    """Run one (model, variant, rep): 4 parallel single-threaded chains."""
    out_dir = RUNS / variant / model / f'rep{rep}'
    rows_path = out_dir / 'rows.csv'
    if (out_dir / 'DONE').exists() and rows_path.exists():
        return list(csv.DictReader(rows_path.open()))
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'build' / f'{model}__{variant}' / 'model'
    if not exe.exists():
        raise RuntimeError(f'missing exe {exe}')
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    t0 = time.time()
    procs = []
    for c in range(CHAINS):
        csv_path = out_dir / f'chain_{c}.csv'
        cmd = [str(exe), f'id={c+1}', 'data', f'file={data}', 'random', f'seed={seed}',
               'output', f'file={csv_path}', 'method=sample',
               f'num_warmup={WARMUP}', f'num_samples={DRAWS}', 'save_warmup=0']
        procs.append((c, csv_path, subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)))
    for c, csv_path, p in procs:
        err = p.communicate()[1]
        if p.returncode != 0:
            raise RuntimeError(f'chain {c} rc={p.returncode}: {err.decode()[:400]}')
    wall = time.time() - t0
    rows = []
    for c, csv_path, _ in procs:
        d = elapsed_from_csv(csv_path)
        d.update(model=model, variant=variant, rep=rep, chain=c,
                 wall_batch_s=round(wall, 3), seed=seed)
        rows.append(d)
    with rows_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variants', default='default,oexp')
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=None)
    ap.add_argument('--compile-only', action='store_true')
    args = ap.parse_args()
    set_env()
    models = [e['model'] for e in MANIFEST]
    if args.models:
        models = [m for m in args.models.split(',') if m]
    variants = [v for v in args.variants.split(',') if v]

    for model in models:
        for variant in variants:
            try:
                exe, secs = compile_model(model, variant)
                print(f'[compile] {model}/{variant}: {"cached" if secs == 0 else f"{secs:.1f}s"}', flush=True)
            except Exception as e:
                print(f'[compile] {model}/{variant}: FAILED {e}', flush=True)
    if args.compile_only:
        return

    for variant in variants:
        for rep in range(args.reps):
            for model in models:
                try:
                    rows = run_config(model, variant, rep)
                    r0 = rows[0]
                    print(f"[run] {variant}/{model}/rep{rep}: wall={r0['wall_batch_s']:.1f}s "
                          f"warm={r0['warmup_s']:.1f} samp={r0['sampling_s']:.1f} "
                          f"div={sum(int(r['divergences']) for r in rows)} "
                          f"lf={sum(int(r['n_leapfrog_total']) for r in rows)}", flush=True)
                except Exception as ex:
                    print(f'[run] {variant}/{model}/rep{rep}: FAILED {ex}', flush=True)
    print('GRID DONE', flush=True)


if __name__ == '__main__':
    main()
