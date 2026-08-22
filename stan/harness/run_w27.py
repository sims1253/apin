#!/usr/bin/env python
"""W-27: BridgeStan model .so CXXFLAGS comparison (default vs -O3[+native]).

Subcommands:
  parity   G1: (logp, grad) on 100 random unconstrained points, default vs variant
  inits    deterministic normal(0,1) inits for models without pf inits
           (kronecker_gp, diamonds): random.Random(f'{seed}-{c}'), 3 reps x 4 chains,
           written once to inits_w27/<model>/rep<r>/chain_<c>.txt (shared by all arms)
  run      G3: single-chain CLI procs (4 parallel), 3 reps x 4 chains,
           seeds 20260819+1000*rep+c, warmup=1000 samples=1000 --metric-window 50,
           identical init files per arm -> runs/w27/<arm>/<model>/rep<r>/
"""
import argparse, csv, os, random, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w27'
STAN_CLI = ROOT / 'external/walnutpie/build_e27/examples/stan_cli'
WARMUP, DRAWS, CHAINS, REPS = 1000, 1000, 4, 3
BASE_SEED = 20260819
MODELS = ['blr', 'arma11', 'hier_2pl', 'kronecker_gp', 'diamonds']
ARMS = {'default': ROOT / 'bs_models', 'o3': ROOT / 'bs_models_o3',
        'o3only': ROOT / 'bs_models_o3only'}

SC_STANZA_RE = re.compile(
    r'total time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
    r'\s*logp_grad calls: (\d+)\s*\n'
    r'\s*time per call: ([\d.eE+-]+)s\s*\n')


def parse_sc(text):
    return [dict(zip(['total', 'logp_time', 'logp_frac', 'logp_calls', 'per_call'],
                     (float(m.group(i)) for i in range(1, 6))))
            for m in SC_STANZA_RE.finditer(text)]


def init_dir_for(model, rep):
    pf = ROOT / 'inits_w25' / model / f'rep{rep}'
    if pf.exists():
        return pf
    return ROOT / 'inits_w27' / model / f'rep{rep}'


def gen_inits():
    import numpy as np
    import bridgestan
    for model in MODELS:
        if (ROOT / 'inits_w25' / model).exists():
            print(f'{model}: pf inits (inits_w25)'); continue
        so = ROOT / 'bs_models' / f'model_{model}.so'
        sm = bridgestan.StanModel(str(so), str(ROOT / f'data/{model}.json'))
        d = sm.param_unc_num()
        for rep in range(REPS):
            seed = BASE_SEED + 1000 * rep
            od = ROOT / 'inits_w27' / model / f'rep{rep}'
            od.mkdir(parents=True, exist_ok=True)
            for c in range(CHAINS):
                rng = random.Random(f'{seed}-{c}')
                vals = [rng.gauss(0.0, 1.0) for _ in range(d)]
                (od / f'chain_{c}.txt').write_text(
                    '\n'.join(repr(v) for v in vals) + '\n')
        print(f'{model}: deterministic normal(0,1) inits -> inits_w27', flush=True)


def parity():
    import numpy as np
    import bridgestan
    ok = True
    for model in MODELS:
        data = str(ROOT / f'data/{model}.json')
        res = {}
        for arm, d in ARMS.items():
            sm = bridgestan.StanModel(str(d / f'model_{model}.so'), data)
            rng = np.random.default_rng(20260822)
            pts = rng.standard_normal((100, sm.param_unc_num()))
            lp, gr = [], []
            for p in pts:
                try:
                    l, g = sm.log_density_gradient(p)
                except Exception:
                    l, g = float('nan'), np.full(sm.param_unc_num(), np.nan)
                lp.append(l); gr.append(g)
            res[arm] = (np.array(lp), np.array(gr), pts)
        base_lp, base_gr, pts = res['default']
        for arm in ('o3', 'o3only'):
            v_lp, v_gr, v_pts = res[arm]
            assert np.array_equal(pts, v_pts)
            finite = np.isfinite(base_lp) & np.isfinite(v_lp)
            dl = np.abs(v_lp - base_lp)
            rel = dl / np.maximum(1.0, np.abs(base_lp))
            gmask = finite[:, None] & np.isfinite(base_gr) & np.isfinite(v_gr)
            gd = np.abs(v_gr - base_gr)
            grel = np.where(gmask, gd / np.maximum(1.0, np.abs(base_gr)), 0.0)
            nbad = int((~np.isfinite(v_lp[finite | ~np.isfinite(base_lp)])).sum()
                       if (~np.isfinite(base_lp)).any() else 0)
            okarm = (rel.max() < 1e-9 and grel.max() < 1e-9
                     and not np.isnan(v_lp[finite]).any()
                     and np.array_equal(np.isfinite(v_lp), np.isfinite(base_lp)))
            ok &= okarm
            print(f'PARITY {model} default-vs-{arm}: '
                  f'max rel logp {rel.max():.3e}, max rel grad {grel.max():.3e}, '
                  f'evaluable pts {int(finite.sum())}/100 -> '
                  + ('PASS' if okarm else 'FAIL'), flush=True)
    print('G1', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def run_arm(model, rep, arm):
    out_dir = RUNS / arm / model / f'rep{rep}'
    if (out_dir / 'DONE').exists() and (out_dir / 'rows.csv').exists():
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    so = ARMS[arm] / f'model_{model}.so'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    init_dir = init_dir_for(model, rep)
    t0 = time.time()
    procs = []
    for c in range(CHAINS):
        csv_path = out_dir / f'chain_{c}.csv'
        cmd = [str(STAN_CLI), str(so), data, '--seed', str(seed + c),
               '--init-file', str(init_dir / f'chain_{c}.txt'),
               '--warmup', str(WARMUP), '--samples', str(DRAWS),
               '--metric-window', '50',
               '--output', str(csv_path)]
        lf = (out_dir / f'chain_{c}.log').open('w')
        procs.append((c, csv_path, subprocess.Popen(
            cmd, stdout=lf, stderr=subprocess.STDOUT,
            env={**os.environ, 'OMP_NUM_THREADS': '1'}), lf))
    for c, csv_path, pr, lf in procs:
        pr.wait(); lf.close()
        if pr.returncode != 0:
            raise RuntimeError(f'{arm}/{model}/rep{rep} chain {c} rc={pr.returncode}')
    wall = time.time() - t0
    rows = []
    for c in range(CHAINS):
        blocks = parse_sc((out_dir / f'chain_{c}.log').read_text())
        warm_b = blocks[0] if blocks else {}
        samp_b = blocks[1] if len(blocks) > 1 else {}
        rows.append(dict(model=model, arm=arm, rep=rep, chain=c,
                         warmup_s=warm_b.get('total'),
                         sampling_s=samp_b.get('total'),
                         logp_time_sampling=samp_b.get('logp_time'),
                         logp_frac_sampling=samp_b.get('logp_frac'),
                         logp_calls_sampling=int(samp_b.get('logp_calls', 0)),
                         us_per_logp_grad=(samp_b.get('per_call') or 0) * 1e6,
                         wall_batch_s=round(wall, 3), seed=seed + c))
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    print(f'[w27] {arm}/{model}/rep{rep}: wall={wall:.1f}s '
          f'sampling_per_call={rows[0]["us_per_logp_grad"]:.1f}us', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['parity', 'inits', 'run'])
    ap.add_argument('--arms', default='default,o3')
    ap.add_argument('--models', default=','.join(MODELS))
    ap.add_argument('--reps', type=int, default=REPS)
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    if args.cmd == 'parity':
        sys.exit(parity())
    if args.cmd == 'inits':
        gen_inits(); return
    for rep in range(args.reps):
        for m in [x for x in args.models.split(',') if x]:
            for arm in [x for x in args.arms.split(',') if x]:
                try:
                    run_arm(m, rep, arm)
                except Exception as ex:
                    print(f'[w27] {arm}/{m}/rep{rep}: FAILED {ex}', flush=True)
    print('W27 RUN DONE', flush=True)


if __name__ == '__main__':
    main()
