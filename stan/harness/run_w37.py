#!/usr/bin/env python
"""W-37 measurement runner: per-window trajectory-geometry series.

Separability pass (pre-registered in WORKLOG W-37): full warmup 1000,
4 chains as 4 SEQUENTIAL single-chain invocations (one process per chain
so the accounting windows are per-chain), seeds 20260819+c, rep0 inits
per the W-36 assignment. WALNUTPIE_GRAD_ACCOUNTING=1, window 50.
samples=100 (separability needs only the warmup series).

Models: EASY {blr, eight_schools_noncentered, arma11} + MARGINAL
{hier_2pl, lsat_model} + kronecker_gp (overhead class).
kronecker_gp chain_0 uses the chain_1 init (E1's recorded deviation for
the known W-36 abort cell).

Outputs: runs/w37/meas/<model>_c<chain>.{csv,log} and
runs/w37/windows.json (parsed per-chain window series).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / 'external/walnutpie_w37/build/examples/stan_cli'
RUNS = ROOT / 'runs/w37'
MODELS_SO = ROOT / 'bs_models_threads'
BASE_SEED = 20260819
WINDOW = 50

MODELS = ['blr', 'eight_schools_noncentered', 'arma11',
          'hier_2pl', 'lsat_model', 'kronecker_gp']
INIT_DIR = {
    'arma11': 'inits_w25', 'blr': 'inits_w25', 'hier_2pl': 'inits_w25',
    'lsat_model': 'inits_w25', 'eight_schools_noncentered': 'inits_w25',
    'kronecker_gp': 'inits_w36',
}
# E1 deviation: kron rep0 chain_0 init aborts (known W-36 failure).
INIT_FILE_OVERRIDE = {('kronecker_gp', 0): 'inits_w36/kronecker_gp/rep0/chain_1.txt'}

WIN_RE = re.compile(
    r'^\[grad-accounting\] window w=(\d+) end=(\d+) macro=(\d+) acc=(\d+) '
    r'sum_h=(\d+) ge1=(\d+) fa=(\d+) fw=(\d+) bl=(\d+) dl=(\d+) exh=(\d+)$')


def run_chain(model, chain, warmup=1000, samples=100, rep=0):
    seed = BASE_SEED + 1000 * rep + chain
    init_rel = INIT_FILE_OVERRIDE.get((model, chain))
    if init_rel is None:
        init_rel = f'{INIT_DIR[model]}/{model}/rep{rep}/chain_{chain}.txt'
    init = ROOT / init_rel
    d = RUNS / 'meas'
    d.mkdir(parents=True, exist_ok=True)
    csv = d / f'{model}_c{chain}.csv'
    csv.unlink(missing_ok=True)
    env = {**os.environ, 'OMP_NUM_THREADS': '1',
           'WALNUTPIE_GRAD_ACCOUNTING': '1',
           'WALNUTPIE_GRAD_WINDOW': str(WINDOW)}
    cmd = [str(CLI), str(MODELS_SO / f'model_{model}.so'),
           str(ROOT / f'data/{model}.json'), '--seed', str(seed),
           '--output', str(csv), '--warmup', str(warmup),
           '--samples', str(samples), '--init-file', str(init)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    log = d / f'{model}_c{chain}.log'
    if p.returncode != 0:
        log.write_text(p.stdout + '\n===STDERR===\n' + p.stderr)
        raise RuntimeError(f'{model} c{chain} rc={p.returncode}: '
                           f'{p.stderr[-500:]}')
    log.write_text(p.stdout)
    wins = []
    for line in p.stdout.splitlines():
        m = WIN_RE.match(line)
        if m:
            w, end, macro, acc, sum_h, ge1, fa, fw, bl, dl, exh = \
                map(int, m.groups())
            wins.append({'w': w, 'end': end, 'macro': macro, 'acc': acc,
                         'sum_h': sum_h, 'ge1': ge1, 'fa': fa, 'fw': fw,
                         'bl': bl, 'dl': dl, 'exh': exh})
    calls = [int(x) for x in re.findall(r'logp_grad calls: (\d+)', p.stdout)]
    return {'seed': seed, 'init': str(init_rel), 'windows': wins,
            'logp_calls': calls}


def main():
    out = {}
    for model in MODELS:
        for chain in range(4):
            tag = f'{model}_c{chain}'
            print(f'run {tag} ...', flush=True)
            try:
                out[tag] = {'model': model, 'chain': chain,
                            **run_chain(model, chain)}
                nw = len(out[tag]['windows'])
                print(f'  {nw} windows, logp_calls={out[tag]["logp_calls"]}')
            except RuntimeError as e:
                out[tag] = {'model': model, 'chain': chain, 'error': str(e)}
                print(f'  FAILED (recorded): {str(e)[:200]}')
    (RUNS / 'windows.json').write_text(json.dumps(out, indent=1))
    print('wrote', RUNS / 'windows.json')


if __name__ == '__main__':
    sys.exit(main())
