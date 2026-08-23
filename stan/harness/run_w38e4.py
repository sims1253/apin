#!/usr/bin/env python3
"""W-38-E4 runner: refinement-aware min-micro-steps (grow-m) adaptation.

Stages (all serialized: 4 chains as 4 sequential single-chain
invocations, OMP_NUM_THREADS=1, env -u LD_LIBRARY_PATH):
  canary   default path of the NEW binary (knobs off) on rep0 cells of
           arma11/blr/hier_2pl (required 12/12) + lsat_model/
           kronecker_gp (bonus 8) -> md5 compared vs the W-38-E2 base
           arm runs (runs/w38e2/base), which were themselves verified
           md5-identical to the exp/safe-adapt-defaults binary.
  micro    grow-rule variant search on blr only, 3 reps x 4 chains,
           warmup=1000 draws=1000: g1 k8-double / g2 k16-double /
           g3 k8-linear (+1). Winner picked by analyze_w38e4.py.
  grid     the winner arm on all 5 models x 3 reps (base arm REUSED
           from runs/w38e2/base — same seeds/inits; legitimacy rests on
           the canary md5s).
  mech     WALNUTPIE_GRAD_ACCOUNTING=1, 1 chain, 1000+1000, seed
           20260819, inits_w25 rep0 chain_0: blr + hier_2pl, off vs
           winner (accepted-h histograms, eval buckets, m histogram).

Outputs: runs/w38e4/{canary,micro,grid,mech}/...
"""
import argparse, csv, hashlib, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w38e4'
CLI = ROOT / 'external/walnutpie_w38e4/build_e4/examples/stan_cli'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr', 'kronecker_gp']
PF_INIT_MODELS = {'arma11', 'blr', 'hier_2pl', 'lsat_model'}  # inits_w25
CANARY_MODELS = ['arma11', 'blr', 'hier_2pl', 'lsat_model', 'kronecker_gp']
GROW_VARIANTS = {
    'g1': ['--grow-min-micro-steps'],
    'g2': ['--grow-min-micro-steps', '--grow-m-streak', '16'],
    'g3': ['--grow-min-micro-steps', '--grow-m-increment', '1'],
    # TUNE arms (pre-registered TUNE branch: smaller cap bounds the
    # damage): all of g1-g3 hard-aborted on blr (nan-grad macro_time).
    't4': ['--grow-min-micro-steps', '--grow-m-cap', '4'],
    't2': ['--grow-min-micro-steps', '--grow-m-cap', '2'],
}
# Winner of the micro-search: g1/g2/g3 (cap 32) and t4 (cap 4) all
# hard-abort on blr (nan-grad macro_time, 9/9+2/3 cells); t2 (cap 2) is
# the only variant completing 3/3 reps — the smallest-cap arm, chosen by
# the pre-registered "ties -> smaller cap-contact" rule.
WINNER_FLAGS = ['--grow-min-micro-steps', '--grow-m-cap', '2']
INIT_DEVIATIONS = {('kronecker_gp', 0, 0): 'chain_1.txt'}  # E1/E2 recorded

SC_STANZA_RE = re.compile(
    r'total time: ([\d.eE+-]+)s?\s*\n'
    r'logp_grad time: ([\d.eE+-]+)s\s*\n'
    r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
    r'\s*logp_grad calls: (\d+)\s*\n'
    r'\s*time per call: ([\d.eE+-]+)s\s*\n')
KV = re.compile(r'(\S+)=(\S+)')


def parse_sc(text):
    return [dict(zip(['total', 'logp_time', 'logp_frac', 'logp_calls',
                      'per_call'],
                     (float(m.group(i)) for i in range(1, 6))))
            for m in SC_STANZA_RE.finditer(text)]


def parse_accounting(text):
    out = {}
    phase = None
    for line in text.splitlines():
        if not line.startswith('[grad-accounting]'):
            continue
        payload = line[len('[grad-accounting]'):].strip()
        if payload.startswith('phase='):
            phase = payload.split('=', 1)[1]
            out[phase] = {}
        elif phase is not None:
            out[phase].update({k: int(v) for k, v in KV.findall(payload)})
    return out


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def init_dir_for(model, rep):
    sub = 'inits_w25' if model in PF_INIT_MODELS else 'inits_w36'
    return ROOT / sub / model / f'rep{rep}'


def run_cell(model, rep, arm, extra, out_root, accounting=False,
             warmup=WARMUP):
    out_dir = out_root / arm / model / f'rep{rep}'
    if (out_dir / 'DONE').exists() and (out_dir / 'rows.csv').exists():
        return str(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    so = ROOT / 'bs_models_threads' / f'model_{model}.so'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    init_dir = init_dir_for(model, rep)
    env = {k: v for k, v in os.environ.items() if k != 'LD_LIBRARY_PATH'}
    env['OMP_NUM_THREADS'] = '1'
    if accounting:
        env['WALNUTPIE_GRAD_ACCOUNTING'] = '1'
    t0 = time.time()
    rows = []
    for c in range(CHAINS):
        csv_path = out_dir / f'chain_{c}.csv'
        init_name = INIT_DEVIATIONS.get((model, rep, c), f'chain_{c}.txt')
        cmd = [str(CLI), str(so), data, '--seed', str(seed + c),
               '--init-file', str(init_dir / init_name),
               '--output', str(csv_path),
               '--warmup', str(warmup), '--samples', str(DRAWS)] + extra
        csv_path.unlink(missing_ok=True)
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
            wall_batch_s=round(time.time() - t0, 3), seed=seed + c,
            csv_md5=md5(csv_path) if csv_path.exists() else None))
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    return str(out_dir)


def run_canary(reps_models):
    """Default path of the new binary; md5 vs the E2 base arm in analyze."""
    for model, rep in reps_models:
        run_cell(model, rep, 'default', [], RUNS / 'canary')


def run_mech():
    """1-chain accounting runs: blr + hier_2pl, off vs winner, 1000+1000."""
    for model in ['blr', 'hier_2pl']:
        for arm, extra in [('off', []), ('grow', WINNER_FLAGS)]:
            out_dir = RUNS / 'mech' / arm / model
            if (out_dir / 'DONE').exists():
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            so = ROOT / 'bs_models_threads' / f'model_{model}.so'
            data = str(ROOT / f'data/{model}.json')
            init = init_dir_for(model, 0) / 'chain_0.txt'
            env = {k: v for k, v in os.environ.items()
                   if k != 'LD_LIBRARY_PATH'}
            env['OMP_NUM_THREADS'] = '1'
            env['WALNUTPIE_GRAD_ACCOUNTING'] = '1'
            csv = out_dir / 'chain_0.csv'
            csv.unlink(missing_ok=True)
            cmd = [str(CLI), str(so), data,
                   '--seed', str(BASE_SEED), '--init-file', str(init),
                   '--output', str(csv), '--warmup', str(WARMUP),
                   '--samples', str(DRAWS)] + extra
            with (out_dir / 'chain_0.log').open('w') as lf:
                p = subprocess.run(cmd, stdout=lf,
                                   stderr=subprocess.STDOUT, env=env)
            if p.returncode != 0:
                raise RuntimeError(f'mech {arm}/{model} rc={p.returncode}')
            (out_dir / 'DONE').write_text('ok')
            print(f'[w38e4] mech/{arm}/{model} done', flush=True)


def cell_summary(out_dir):
    rows = list(csv.DictReader((Path(out_dir) / 'rows.csv').open()))
    calls = sum(int(r['logp_calls_warm']) + int(r['logp_calls_samp'])
                for r in rows)
    return rows[0]['wall_batch_s'], calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='canary,micro,grid,mech')
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=','.join(MODELS))
    args = ap.parse_args()
    stages = args.stage.split(',')
    models = [m for m in args.models.split(',') if m]
    os.environ['OMP_NUM_THREADS'] = '1'

    if 'canary' in stages:
        run_canary([(m, 0) for m in CANARY_MODELS])
        print('[w38e4] canary cells done', flush=True)
    if 'micro' in stages:
        for rep in range(args.reps):
            for arm, extra in GROW_VARIANTS.items():
                t0 = time.time()
                try:
                    d = run_cell('blr', rep, arm, extra, RUNS / 'micro')
                    wall, calls = cell_summary(d)
                    print(f'[w38e4] micro/{arm}/blr/rep{rep}: '
                          f'wall={wall}s calls={calls} '
                          f'({time.time()-t0:.1f}s)', flush=True)
                except Exception as ex:
                    print(f'[w38e4] micro/{arm}/blr/rep{rep}: FAILED {ex}',
                          flush=True)
    if 'grid' in stages:
        for rep in range(args.reps):
            for m in models:
                t0 = time.time()
                try:
                    d = run_cell(m, rep, 'grow', WINNER_FLAGS, RUNS / 'grid')
                    wall, calls = cell_summary(d)
                    print(f'[w38e4] grid/grow/{m}/rep{rep}: wall={wall}s '
                          f'calls={calls} ({time.time()-t0:.1f}s)',
                          flush=True)
                except Exception as ex:
                    print(f'[w38e4] grid/grow/{m}/rep{rep}: FAILED {ex}',
                          flush=True)
    if 'mech' in stages:
        run_mech()
    print('W38E4 STAGES DONE', flush=True)


if __name__ == '__main__':
    main()
