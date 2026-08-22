#!/usr/bin/env python
"""W-31 runner: safe default cross-chain tolerances in the controller.

Arms (both with --metric-window 50, pf inits from inits_w25/, matching
the W-25 base arm so ESS is directly comparable):
  mc_default   --chains 4, all default flags (W-31 safe default: no
                early exit) — gate (b)
  mc_earlyexit --chains 4 --early-exit (opt-in restoring the pre-W-31
                default cross-chain tols) — gate (c)

Seeds 20260819+1000*rep (+c per chain via the mc seeding). Writes
runs/w31/<arm>/<model>/rep<r>/chain_<c>.csv + mc.log + rows.csv
(schema compatible with the W-25 walks).
"""
import argparse, csv, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'
STAN_CLI = ROOT / 'external/walnutpie/build/examples/stan_cli'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819

MC_STANZA_RE = re.compile(
    r'chain (\d+)\s+total time: ([\d.eE+-]+)s\s*\n'
    r'chain \1 logp_grad time: ([\d.eE+-]+)s\s*\n'
    r'chain \1 logp_grad fraction: ([\d.eE+-]+)\s*\n'
    r'chain \1\s+logp_grad calls: (\d+)\s*\n'
    r'chain \1\s+time per call: ([\d.eE+-]+)s\s*\n')

ARMS = {
    'mc_default': [],
    'mc_earlyexit': ['--early-exit'],
}


def parse_mc(text):
    out = {}
    for m in MC_STANZA_RE.finditer(text):
        c = int(m.group(1))
        out.setdefault(c, []).append(dict(
            zip(['total', 'logp_time', 'logp_frac', 'logp_calls', 'per_call'],
                (float(m.group(i)) for i in range(2, 7)))))
    return out


def run_arm(model, rep, arm, so_dir):
    out_dir = RUNS / 'w31' / arm / model / f'rep{rep}'
    if (out_dir / 'DONE').exists():
        return str(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    so = so_dir / f'model_{model}.so'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    init_dir = ROOT / 'inits_w25' / model / f'rep{rep}'
    out_pat = str(out_dir / 'chain_{c}.csv')
    cmd = [str(STAN_CLI), str(so), data, '--seed', str(seed),
           '--chains', str(CHAINS),
           '--init-file', str(init_dir / 'chain_{c}.txt'),
           '--output', out_pat,
           '--warmup', str(WARMUP), '--samples', str(DRAWS),
           '--metric-window', '50'] + ARMS[arm]
    t0 = time.time()
    log = out_dir / 'mc.log'
    with log.open('w') as lf:
        p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                           env={**os.environ, 'OMP_NUM_THREADS': '1'})
    if p.returncode != 0:
        raise RuntimeError(f'{arm}/{model}/rep{rep} rc={p.returncode}, see {log}')
    text = log.read_text()
    em = re.search(r'controller exit_iter=(\d+) early_exit=(\d+)', text)
    exit_iter = int(em.group(1)) if em else None
    early = int(em.group(2)) if em else None
    wall = time.time() - t0
    rows = []
    for c, blocks in sorted(parse_mc(text).items()):
        warm_b = blocks[0] if blocks else {}
        samp_b = blocks[1] if len(blocks) > 1 else {}
        rows.append(dict(model=model, variant=arm, rep=rep, chain=c,
                         warmup_s=warm_b.get('total'),
                         sampling_s=samp_b.get('total'), n_draws=DRAWS,
                         n_leapfrog_total=int(warm_b.get('logp_calls', 0) +
                                              samp_b.get('logp_calls', 0)),
                         n_leapfrog_sampling=int(samp_b.get('logp_calls', 0)),
                         wall_batch_s=round(wall, 3), seed=seed,
                         exit_iter=exit_iter, early_exit=early))
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    return str(out_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default='eight_schools_noncentered,hier_2pl')
    ap.add_argument('--so-dir', default=str(ROOT / 'bs_models_threads'))
    ap.add_argument('--arms', default='mc_default,mc_earlyexit')
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    so_dir = Path(args.so_dir)
    for arm in args.arms.split(','):
        for model in [m for m in args.models.split(',') if m]:
            if not (so_dir / f'model_{model}.so').exists():
                print(f'[w31] {model}: SKIP (no .so)', flush=True)
                continue
            for rep in range(args.reps):
                try:
                    t0 = time.time()
                    d = run_arm(model, rep, arm, so_dir)
                    rows = list(csv.DictReader((Path(d) / 'rows.csv').open()))
                    r0 = rows[0]
                    print(f'[w31] {arm}/{model}/rep{rep}: '
                          f'exit_iter={r0["exit_iter"]} early_exit={r0["early_exit"]} '
                          f'wall={r0["wall_batch_s"]}s ({time.time()-t0:.1f}s)',
                          flush=True)
                except Exception as ex:
                    print(f'[w31] {arm}/{model}/rep{rep}: FAILED {ex}',
                          flush=True)
    print('W31 GRID DONE', flush=True)


if __name__ == '__main__':
    main()
