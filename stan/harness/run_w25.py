#!/usr/bin/env python
"""W-25 runner: library-level warmup early-exit (multi-chain controller).

Arms (all with --metric-window 50 so successive step snapshots are
independent window estimates, identical across arms):
  base      4 single-chain CLI procs, fixed warmup 1000 (default code path)
  mc_nogate --chains 4, temporal gate OFF (controller cross-chain exit only)
  mc_gate05 --chains 4, --temporal-step-tol 0.05 (window 50, min-iter 200)

Seeds 20260819+1000*rep+c (mc: process seed 20260819+1000*rep, per-chain
models seed+c replicate the per-chain streams). Writes runs/<tag>/<model>/
rep<r>/chain_<c>.csv + rows.csv (schema compatible with compute_ess walks).
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

SC_STANZA_RE = re.compile(
    r'total time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
    r'\s*logp_grad calls: (\d+)\s*\n'
    r'\s*time per call: ([\d.eE+-]+)s\s*\n')


def parse_mc(text):
    out = {}
    for m in MC_STANZA_RE.finditer(text):
        c = int(m.group(1))
        out.setdefault(c, []).append(dict(
            zip(['total', 'logp_time', 'logp_frac', 'logp_calls', 'per_call'],
                (float(m.group(i)) for i in range(2, 7)))))
    return out


def parse_sc(text):
    return [dict(zip(['total', 'logp_time', 'logp_frac', 'logp_calls', 'per_call'],
                     (float(m.group(i)) for i in range(1, 6))))
            for m in SC_STANZA_RE.finditer(text)]


def rows_from(timing_by_chain, model, tag, rep, wall, seed, exit_iters,
              extras=None):
    rows = []
    for c in sorted(timing_by_chain):
        blocks = timing_by_chain[c]
        warm_b = blocks[0] if blocks else {}
        samp_b = blocks[1] if len(blocks) > 1 else {}
        row = dict(model=model, variant=tag, rep=rep, chain=c,
                   warmup_s=warm_b.get('total'),
                   sampling_s=samp_b.get('total'),
                   n_draws=DRAWS,
                   n_leapfrog_total=int(warm_b.get('logp_calls', 0) + samp_b.get('logp_calls', 0)),
                   n_leapfrog_sampling=int(samp_b.get('logp_calls', 0)),
                   divergences=-1, treedepth_hits=-1,
                   stepsize_final=None, accept_mean=None, lp_mean=None,
                   logp_frac_sampling=samp_b.get('logp_frac'),
                   us_per_logp_grad=samp_b.get('per_call', 0) * 1e6 if samp_b.get('per_call') else None,
                   wall_batch_s=round(wall, 3), seed=seed,
                   exit_iter=exit_iters.get(c))
        if extras:
            row.update(extras)
        rows.append(row)
    return rows


def write_rows(out_dir, rows):
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')


def run_arm(model, rep, tag, so_dir, mc, temporal_tol=None, pilot=0):
    out_dir = RUNS / tag / model / f'rep{rep}'
    if (out_dir / 'DONE').exists() and (out_dir / 'rows.csv').exists():
        return str(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    so = so_dir / f'model_{model}.so'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    init_dir = ROOT / 'inits_w25' / model / f'rep{rep}'
    common = ['--warmup', str(WARMUP), '--samples', str(DRAWS), '--metric-window', '50']
    t0 = time.time()
    if mc:
        out_pat = str(out_dir / 'chain_{c}.csv')
        cmd = [str(STAN_CLI), str(so), data, '--seed', str(seed), '--chains', str(CHAINS),
               '--temporal-step-tol', str(temporal_tol if temporal_tol is not None else 0.0),
               '--init-file', str(init_dir / 'chain_{c}.txt'),
               '--output', out_pat] + common
        if pilot:
            cmd += ['--pilot-burst', str(pilot)]
        log = (out_dir / 'mc.log')
        with log.open('w') as lf:
            p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env={**os.environ, 'OMP_NUM_THREADS': '1'})
        if p.returncode != 0:
            raise RuntimeError(f'{tag}/{model}/rep{rep} rc={p.returncode}, see {log}')
        text = log.read_text()
        timing = parse_mc(text)
        em = re.search(r'controller exit_iter=(\d+) early_exit=(\d+)', text)
        exit_iters = {c: int(em.group(1)) for c in timing} if em else {}
        wall = time.time() - t0
        # W-28 pilot-arm extras: per-check stats + totals from the pilot lines
        extras = {}
        checks = re.findall(
            r'pilot check (\d+) at iter (\d+): rho1_max=([\d.eE+-]+) '
            r'rhat_lp=([\d.eE+-]+) -> (\w+)', text)
        if checks:
            extras['pilot_checks'] = int(checks[-1][0])
            extras['pilot_last_rho1_max'] = float(checks[-1][2])
            extras['pilot_last_rhat_lp'] = float(checks[-1][3])
            extras['pilot_last_decision'] = checks[-1][4]
            extras['pilot_first_iter'] = int(checks[0][1])
        rows = rows_from(timing, model, tag, rep, wall, seed, exit_iters, extras)
    else:
        procs = []
        for c in range(CHAINS):
            csv_path = out_dir / f'chain_{c}.csv'
            cmd = [str(STAN_CLI), str(so), data, '--seed', str(seed + c),
                   '--init-file', str(init_dir / f'chain_{c}.txt'),
                   '--output', str(csv_path)] + common
            lf = (out_dir / f'chain_{c}.log').open('w')
            procs.append((c, csv_path, subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT), lf))
        timing, exit_iters = {}, {}
        for c, csv_path, pr, lf in procs:
            pr.wait(); lf.close()
            if pr.returncode != 0:
                raise RuntimeError(f'{tag}/{model}/rep{rep} chain {c} rc={pr.returncode}')
            timing[c] = parse_sc((out_dir / f'chain_{c}.log').read_text())
        wall = time.time() - t0
        rows = rows_from(timing, model, tag, rep, wall, seed, exit_iters)
    write_rows(out_dir, rows)
    return str(out_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default='arma11,lsat_model,hier_2pl,blr,eight_schools_noncentered')
    ap.add_argument('--so-dir', default=str(ROOT / 'bs_models_threads'))
    ap.add_argument('--arms', default='base,mc_nogate,mc_gate05')
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    models = [m for m in args.models.split(',') if m]
    arm_cfg = {'base': dict(mc=False), 'mc_nogate': dict(mc=True, temporal_tol=None),
               'mc_gate05': dict(mc=True, temporal_tol=0.05),
               'mc_pilot50': dict(mc=True, temporal_tol=0.05, pilot=50)}
    for rep in range(args.reps):
        for m in models:
            if not (Path(args.so_dir) / f'model_{m}.so').exists():
                print(f'[w25] {m}: SKIP (no .so)', flush=True); continue
            for arm in args.arms.split(','):
                try:
                    t0 = time.time()
                    d = run_arm(m, rep, arm, Path(args.so_dir), **arm_cfg[arm])
                    rows = list(csv.DictReader((Path(d) / 'rows.csv').open()))
                    r0 = rows[0]
                    print(f'[w25] {arm}/{m}/rep{rep}: wall={r0["wall_batch_s"]}s '
                          f'warm={r0["warmup_s"]} exit_iter={r0["exit_iter"]} '
                          f'({time.time()-t0:.1f}s)', flush=True)
                except Exception as ex:
                    print(f'[w25] {arm}/{m}/rep{rep}: FAILED {ex}', flush=True)
    print('W25 GRID DONE', flush=True)


if __name__ == '__main__':
    main()
