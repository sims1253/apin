#!/usr/bin/env python
"""W-38-E2 runner: error-discipline ablation, warmup-weighted.

Arms (all warmup=1000 draws=1000, 4 SEQUENTIAL single-chain invocations,
3 reps, seeds 20260819+1000*rep+c, identical inits per model/rep/chain):
  base  CLI defaults (also the canary reference arm)
  e2a   --max-error-start 5.0 --max-error-iters 950   (existing knob)
  e2b   --warmup-max-step-halvings 3                  (new knob, W-38-E2)
  e2c   --warmup-max-error 5.0                        (new knob, W-38-E2)
Probe (blr only, warmup=400 draws=1000): probe_base / probe_e2a5 /
probe_e2a8 (--max-error-start 1e8 --max-error-iters 950).

Canary: ref binary = external/walnutpie/build_w36exp/examples/stan_cli
(exp/safe-adapt-defaults @ 43b6435) rerun on base-arm cells of 3 models
rep0 -> runs/w38e2/refcanary/; md5 compared by analyze_w38e2.py.

Outputs: runs/w38e2/<arm>/<model>/rep<r>/{chain_<c>.csv,chain_<c>.log,
rows.csv,DONE}; probe under runs/w38e2/probe/<arm>/blr/rep<r>/.
"""
import argparse, csv, hashlib, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w38e2'
CLI = ROOT / 'external/walnutpie_w38e2/build_e2/examples/stan_cli'
REF_CLI = ROOT / 'external/walnutpie/build_w36exp/examples/stan_cli'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr', 'kronecker_gp']
PF_INIT_MODELS = {'arma11', 'blr', 'hier_2pl', 'lsat_model'}  # inits_w25
ARMS = {
    'base': [],
    'e2a': ['--max-error-start', '5.0', '--max-error-iters', '950'],
    'e2b': ['--warmup-max-step-halvings', '3'],
    'e2c': ['--warmup-max-error', '5.0'],
}
PROBE_ARMS = {
    'probe_base': [],
    'probe_e2a5': ['--max-error-start', '5.0', '--max-error-iters', '950'],
    'probe_e2a8': ['--max-error-start', '1e8', '--max-error-iters', '950'],
}
CANARY_MODELS = ['arma11', 'blr', 'hier_2pl']
# RECORDED DEVIATION (matches E1's, results/grad_accounting_w38.md): the
# kronecker_gp rep0 chain_0 deterministic init triggers the KNOWN
# pre-existing W-36 abort ("macro_time must be in (0, inf)" after nan
# eigenvectors_sym gradients) under every seed tried (init-dependent,
# seed-independent: 20260819/20260820 both abort); rep1/rep2 chain_0 and
# all other chains are fine. That one cell uses the chain_1 init file.
INIT_DEVIATIONS = {('kronecker_gp', 0, 0): 'chain_1.txt'}

SC_STANZA_RE = re.compile(
    r'total time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
    r'\s*logp_grad calls: (\d+)\s*\n'
    r'\s*time per call: ([\d.eE+-]+)s\s*\n')


def parse_sc(text):
    return [dict(zip(['total', 'logp_time', 'logp_frac', 'logp_calls',
                      'per_call'],
                     (float(m.group(i)) for i in range(1, 6))))
            for m in SC_STANZA_RE.finditer(text)]


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def init_dir_for(model, rep):
    sub = 'inits_w25' if model in PF_INIT_MODELS else 'inits_w36'
    return ROOT / sub / model / f'rep{rep}'


def run_cell(model, rep, arm, extra, warmup, out_root):
    out_dir = out_root / arm / model / f'rep{rep}'
    if (out_dir / 'DONE').exists() and (out_dir / 'rows.csv').exists():
        return str(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    so = ROOT / 'bs_models_threads' / f'model_{model}.so'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    init_dir = init_dir_for(model, rep)
    env = {**os.environ, 'OMP_NUM_THREADS': '1'}
    t0 = time.time()
    rows = []
    for c in range(CHAINS):
        csv_path = out_dir / f'chain_{c}.csv'
        init_name = INIT_DEVIATIONS.get((model, rep, c), f'chain_{c}.txt')
        cmd = [str(CLI), str(so), data, '--seed', str(seed + c),
               '--init-file', str(init_dir / init_name),
               '--output', str(csv_path),
               '--warmup', str(warmup), '--samples', str(DRAWS)] + extra
        lf_path = out_dir / f'chain_{c}.log'
        with lf_path.open('w') as lf:
            p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                               env=env)
        if p.returncode != 0:
            raise RuntimeError(f'{arm}/{model}/rep{rep} c{c} rc={p.returncode}')
        blocks = parse_sc(lf_path.read_text())
        warm_b = blocks[0] if blocks else {}
        samp_b = blocks[1] if len(blocks) > 1 else {}
        rows.append(dict(
            model=model, arm=arm, rep=rep, chain=c,
            warmup_s=warm_b.get('total'), sampling_s=samp_b.get('total'),
            logp_calls_warm=int(warm_b.get('logp_calls', 0)),
            logp_calls_samp=int(samp_b.get('logp_calls', 0)),
            us_per_logp_warm=(warm_b.get('per_call', 0) * 1e6
                              if warm_b.get('per_call') else None),
            us_per_logp_samp=(samp_b.get('per_call', 0) * 1e6
                              if samp_b.get('per_call') else None),
            wall_batch_s=round(time.time() - t0, 3), seed=seed + c,
            csv_md5=md5(csv_path) if csv_path.exists() else None))
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    return str(out_dir)


def run_canary(reps_models):
    """Re-run the PRE-CHANGE binary (build_w36exp @ 43b6435) on the base
    command lines of the canary models; md5 compared in analysis."""
    for model, rep in reps_models:
        out_dir = RUNS / 'refcanary' / model / f'rep{rep}'
        if (out_dir / 'DONE').exists():
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        so = ROOT / 'bs_models_threads' / f'model_{model}.so'
        data = str(ROOT / f'data/{model}.json')
        seed = BASE_SEED + 1000 * rep
        init_dir = init_dir_for(model, rep)
        env = {**os.environ, 'OMP_NUM_THREADS': '1'}
        for c in range(CHAINS):
            csv_path = out_dir / f'chain_{c}.csv'
            cmd = [str(REF_CLI), str(so), data, '--seed', str(seed + c),
                   '--init-file', str(init_dir / f'chain_{c}.txt'),
                   '--output', str(csv_path),
                   '--warmup', str(WARMUP), '--samples', str(DRAWS)]
            with (out_dir / f'chain_{c}.log').open('w') as lf:
                p = subprocess.run(cmd, stdout=lf,
                                   stderr=subprocess.STDOUT, env=env)
            if p.returncode != 0:
                raise RuntimeError(f'refcanary/{model}/rep{rep} c{c} rc={p.returncode}')
        (out_dir / 'DONE').write_text('ok')
        print(f'[w38e2] refcanary/{model}/rep{rep} done', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=','.join(MODELS))
    ap.add_argument('--arms', default=','.join(ARMS))
    ap.add_argument('--probe', action='store_true',
                    help='run the blr short-warmup probe (warmup=400)')
    ap.add_argument('--canary', action='store_true',
                    help='run the pre-change reference binary cells')
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    models = [m for m in args.models.split(',') if m]
    arms = [a for a in args.arms.split(',') if a]
    if args.canary:
        run_canary([(m, 0) for m in CANARY_MODELS])
    for rep in range(args.reps):
        for m in models:
            for arm in arms:
                t0 = time.time()
                try:
                    run_cell(m, rep, arm, ARMS[arm], WARMUP, RUNS)
                    rows = list(csv.DictReader(
                        (RUNS / arm / m / f'rep{rep}' / 'rows.csv').open()))
                    r0 = rows[0]
                    calls = sum(int(r['logp_calls_warm']) +
                                int(r['logp_calls_samp']) for r in rows)
                    print(f'[w38e2] {arm}/{m}/rep{rep}: '
                          f'wall={r0["wall_batch_s"]}s calls={calls} '
                          f'({time.time()-t0:.1f}s)', flush=True)
                except Exception as ex:
                    print(f'[w38e2] {arm}/{m}/rep{rep}: FAILED {ex}',
                          flush=True)
    if args.probe:
        for rep in range(args.reps):
            for arm in PROBE_ARMS:
                t0 = time.time()
                try:
                    run_cell('blr', rep, arm, PROBE_ARMS[arm], 400,
                             RUNS / 'probe')
                    rows = list(csv.DictReader(
                        (RUNS / 'probe' / arm / 'blr' / f'rep{rep}' /
                         'rows.csv').open()))
                    calls = sum(int(r['logp_calls_warm']) +
                                int(r['logp_calls_samp']) for r in rows)
                    print(f'[w38e2] probe/{arm}/blr/rep{rep}: '
                          f'wall={rows[0]["wall_batch_s"]}s calls={calls} '
                          f'({time.time()-t0:.1f}s)', flush=True)
                except Exception as ex:
                    print(f'[w38e2] probe/{arm}/blr/rep{rep}: FAILED {ex}',
                          flush=True)
    print('W38E2 GRID DONE', flush=True)


if __name__ == '__main__':
    main()
