#!/usr/bin/env python
"""nutpie baseline runner: CORE_SET models, 4 chains, 1000 tune + 1000 draws.

nutpie 0.16 API: compile_stan_model(filename=...) -> .with_data(**data) -> sample(...).
Writes cmdstan-style per-chain CSVs + rows.csv compatible with run_grid outputs.
"""
import argparse, csv, json, os, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / 'harness/core_manifest.json').read_text())
RUNS = ROOT / 'runs'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
MAX_DEPTH = 10


def stan_name(name, idx):
    if idx is None:
        return name
    return name + '.' + '.'.join(str(i + 1) for i in idx)


def extract_params(post):
    """-> {col_name: (chains, draws) array}, model params only (drop *_trans)."""
    out = {}
    import numpy as np
    for vn in list(post.data_vars):
        if vn.startswith('transformation'):
            continue
        arr = post[vn].values
        if arr.ndim == 2:
            out[stan_name(vn, None)] = arr
        else:
            flat = arr.reshape(arr.shape[0], arr.shape[1], -1)
            shape_tail = arr.shape[2:]
            for k in range(flat.shape[2]):
                idx = np.unravel_index(k, shape_tail)
                out[stan_name(vn, idx)] = flat[:, :, k]
    return out


def run_config(model, rep, compiled_cache, nutpie):
    out_dir = RUNS / 'nutpie' / model / f'rep{rep}'
    rows_path = out_dir / 'rows.csv'
    if (out_dir / 'DONE').exists() and rows_path.exists():
        return list(csv.DictReader(rows_path.open()))
    out_dir.mkdir(parents=True, exist_ok=True)

    if model not in compiled_cache:
        t0 = time.time()
        data = json.loads((ROOT / f'data/{model}.json').read_text())
        c = nutpie.compile_stan_model(filename=str(ROOT / f'models/{model}.stan'))
        c = c.with_data(**data)
        compiled_cache[model] = c
        print(f'[nutpie-compile] {model}: {time.time()-t0:.1f}s', flush=True)
    compiled = compiled_cache[model]

    seed = BASE_SEED + 1000 * rep
    t0 = time.time()
    res = nutpie.sample(compiled, chains=CHAINS, tune=WARMUP, draws=DRAWS,
                        seed=seed, cores=CHAINS, save_warmup=False, progress_bar=False)
    wall = time.time() - t0

    post = res['posterior']; ss = res['sample_stats']
    params = extract_params(post)
    n_draws = post.sizes['draw']

    lp = ss['logp'].values if 'logp' in ss else None
    accept = ss['mean_tree_accept'].values if 'mean_tree_accept' in ss else None
    step = ss['step_size'].values if 'step_size' in ss else None
    depth = ss['depth'].values if 'depth' in ss else None
    lf = ss['n_steps'].values if 'n_steps' in ss else None
    div = ss['diverging'].values if 'diverging' in ss else None
    energy = ss['energy'].values if 'energy' in ss else None
    maxdepth = ss['maxdepth_reached'].values if 'maxdepth_reached' in ss else None

    def fnum(x):
        return repr(float(x)) if x is not None else 'NA'

    rows = []
    lf_total = int(lf.sum()) if lf is not None else -1
    div_total = int(div.sum()) if div is not None else -1
    td_total = int(maxdepth.sum()) if maxdepth is not None else (
        int((depth >= MAX_DEPTH).sum()) if depth is not None else -1)
    for c in range(CHAINS):
        f = out_dir / f'chain_{c}.csv'
        cols = list(params.keys()) + ['lp__', 'accept_stat__', 'stepsize__',
                                      'treedepth__', 'n_leapfrog__', 'divergent__', 'energy__']
        with f.open('w') as fh:
            fh.write(f'# model = {model} (nutpie)\n')
            fh.write(f'# Elapsed Time: NA seconds (Warm-up), NA seconds (Sampling)\n')
            fh.write(','.join(cols) + '\n')
            for i in range(n_draws):
                vals = [fnum(params[k][c, i]) for k in params]
                vals += [fnum(lp[c, i]), fnum(accept[c, i]), fnum(step[c, i]),
                         fnum(depth[c, i]), fnum(lf[c, i]), fnum(div[c, i]), fnum(energy[c, i])]
                fh.write(','.join(vals) + '\n')
        rows.append(dict(model=model, variant='nutpie', rep=rep, chain=c,
                         warmup_s=None, sampling_s=None, n_draws=n_draws,
                         n_leapfrog_total=lf_total, n_leapfrog_sampling=lf_total,
                         divergences=div_total, treedepth_hits=td_total,
                         stepsize_final=None, accept_mean=None, lp_mean=None,
                         wall_batch_s=round(wall, 3), seed=seed))
    with rows_path.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=None)
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    import nutpie
    models = [e['model'] for e in MANIFEST]
    if args.models:
        models = [m for m in args.models.split(',') if m]
    cache = {}
    for rep in range(args.reps):
        for model in models:
            try:
                rows = run_config(model, rep, cache, nutpie)
                print(f"[run] nutpie/{model}/rep{rep}: wall={rows[0]['wall_batch_s']:.1f}s "
                      f"div={sum(int(r['divergences']) for r in rows)} "
                      f"lf={sum(int(r['n_leapfrog_total']) for r in rows)//CHAINS}", flush=True)
            except Exception as ex:
                print(f'[run] nutpie/{model}/rep{rep}: FAILED {ex}', flush=True)
                traceback.print_exc()
    print('NUTPIE GRID DONE', flush=True)


if __name__ == '__main__':
    main()
