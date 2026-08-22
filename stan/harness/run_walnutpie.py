#!/usr/bin/env python
"""walnutpie (WALNUTS, arXiv 2506.18746) baseline runner.

stan_cli consumes bridgestan .so models; single chain per invocation, so run
4 in parallel (1 core each) with per-chain seeds. Parses the CLI's printed
timing blocks (warmup + sampling: total time, logp_grad time, logp_grad calls)
and the draws CSV (model params only -> ess.R).
"""
import argparse, csv, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'
STAN_CLI = ROOT / 'external/walnutpie/build/examples/stan_cli'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819

STANZA_RE = re.compile(
    r'total time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
    r'\s*logp_grad calls: (\d+)\s*\n'
    r'\s*time per call: ([\d.eE+-]+)s?\s*\n')

def parse_timing(text):
    """stan_cli prints the 5-line timing stanza twice (warmup, sampling)."""
    return [dict(zip(['total', 'logp_time', 'logp_frac', 'logp_calls', 'per_call'],
                     (float(m.group(i)) for i in range(1, 6))))
            for m in STANZA_RE.finditer(text)]

def run_config(model, rep, tag='walnut', extra_flags=None, init_file_dir=None, warmup=None, draws=None):
    out_dir = RUNS / tag / model / f'rep{rep}'
    rows_path = out_dir / 'rows.csv'
    if (out_dir / 'DONE').exists() and rows_path.exists():
        return list(csv.DictReader(rows_path.open()))
    out_dir.mkdir(parents=True, exist_ok=True)
    so = ROOT / 'bs_models' / f'model_{model}.so'
    if not so.exists():
        raise RuntimeError(f'missing .so {so}')
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    t0 = time.time()
    procs = []
    for c in range(CHAINS):
        csv_path = out_dir / f'chain_{c}.csv'
        cmd = [str(STAN_CLI), str(so), data,
               '--seed', str(seed + c), '--warmup', str(warmup or WARMUP),
               '--samples', str(draws or DRAWS), '--output', str(csv_path)] + (extra_flags or [])
        if init_file_dir:
            base = Path(init_file_dir)
            init_f = base / model / f'rep{rep}' / f'chain_{c}.txt'
            if not init_f.exists():
                init_f = base / f'rep{rep}' / f'chain_{c}.txt'
            cmd += ['--init-file', str(init_f)]
        log_f = open(out_dir / f'chain_{c}.log', 'w')
        procs.append((c, csv_path, subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT), log_f))
    timing = {}
    for c, csv_path, p, log_f in procs:
        p.wait(); log_f.close()
        if p.returncode != 0:
            raise RuntimeError(f'chain {c} rc={p.returncode}, see {out_dir}/chain_{c}.log')
        blocks = parse_timing((out_dir / f'chain_{c}.log').read_text())
        timing[c] = blocks
    wall = time.time() - t0

    rows = []
    for c, csv_path, _, _ in procs:
        blocks = timing[c]
        warm_b = blocks[0] if blocks else {}
        samp_b = blocks[1] if len(blocks) > 1 else {}
        n_rows = sum(1 for _ in open(csv_path)) - 1 if csv_path.exists() else 0
        rows.append(dict(model=model, variant=tag, rep=rep, chain=c,
                         warmup_s=warm_b.get('total'), sampling_s=samp_b.get('total'),
                         n_draws=n_rows,
                         n_leapfrog_total=int(warm_b.get('logp_calls', 0) + samp_b.get('logp_calls', 0)),
                         n_leapfrog_sampling=int(samp_b.get('logp_calls', 0)),
                         divergences=-1, treedepth_hits=-1,
                         stepsize_final=None, accept_mean=None, lp_mean=None,
                         logp_frac_sampling=samp_b.get('logp_frac'),
                         us_per_logp_grad=samp_b.get('per_call', 0) * 1e6 if samp_b.get('per_call') else None,
                         wall_batch_s=round(wall, 3), seed=seed))
    with rows_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=None)
    ap.add_argument('--tag', default='walnut')
    ap.add_argument('--optimizer', default=None)
    ap.add_argument('--batch-stride', type=int, default=None)
    ap.add_argument('--grad-clip', type=float, default=None)
    ap.add_argument('--da-freeze-average', action='store_true')
    ap.add_argument('--mass-shrink-kappa', type=float, default=None)
    ap.add_argument('--mass-var-floor', type=float, default=None)
    ap.add_argument('--max-macro-steps', type=float, default=None)
    ap.add_argument('--max-trajectory-doublings', type=int, default=None)
    ap.add_argument('--extra-flags', default=None, help='raw passthrough to stan_cli')
    ap.add_argument('--metric-mode', default=None, choices=['diag','fold','full'])
    ap.add_argument('--warmup', type=int, default=None)
    ap.add_argument('--draws', type=int, default=None)
    ap.add_argument('--init-file-dir', default=None,
                    help='dir with per-chain init files chain_<c>.txt per rep subdirs rep<r>')
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    manifest = json.loads((ROOT / 'harness/core_manifest.json').read_text())
    models = [e['model'] for e in manifest]
    if args.models:
        models = [m for m in args.models.split(',') if m]
    flags = []
    if args.optimizer:
        flags += ['--step-optimizer', args.optimizer]
    if args.batch_stride:
        flags += ['--step-opt-batch-stride', str(args.batch_stride)]
    if args.grad_clip is not None:
        flags += ['--step-grad-clip', str(args.grad_clip)]
    if args.da_freeze_average:
        flags += ['--da-freeze-average']
    if args.mass_shrink_kappa is not None:
        flags += ['--mass-shrink-kappa', str(args.mass_shrink_kappa)]
    if args.mass_var_floor is not None:
        flags += ['--mass-var-floor', str(args.mass_var_floor)]
    if args.max_macro_steps is not None:
        flags += ['--max-macro-steps-target', str(args.max_macro_steps)]
    if args.max_trajectory_doublings is not None:
        flags += ['--max-trajectory-doublings', str(args.max_trajectory_doublings)]
    if args.extra_flags:
        flags += args.extra_flags.split()
    if args.metric_mode == 'fold':
        flags += ['--metric-rank', '10']
    elif args.metric_mode == 'full':
        flags += ['--metric-rank', '10', '--metric-full']
    for rep in range(args.reps):
        for m in models:
            if not (ROOT / 'bs_models' / f'model_{m}.so').exists():
                print(f'[run] {args.tag}/{m}/rep{rep}: SKIP (no .so)', flush=True)
                continue
            try:
                rows = run_config(m, rep, tag=args.tag, extra_flags=flags, init_file_dir=args.init_file_dir, warmup=args.warmup, draws=args.draws)
                r0 = rows[0]
                print(f"[run] {args.tag}/{m}/rep{rep}: wall={r0['wall_batch_s']:.1f}s "
                      f"warm={r0['warmup_s']:.1f} samp={r0['sampling_s']:.1f} "
                      f"lg={sum(int(r['n_leapfrog_total']) for r in rows)} "
                      f"logp_frac={r0['logp_frac_sampling']}", flush=True)
            except Exception as ex:
                print(f'[run] {args.tag}/{m}/rep{rep}: FAILED {ex}', flush=True)
    print(f'{args.tag.upper()} GRID DONE', flush=True)

if __name__ == '__main__':
    main()
