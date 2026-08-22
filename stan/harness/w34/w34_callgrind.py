#!/usr/bin/env python
"""W-34 gate (b): callgrind Ir per gradient, stock vs armB hier_2pl .so.

W-29 protocol verbatim (warmup 100 samples 50, seed 20260819, pf init
inits_w25/hier_2pl/rep0/chain_0.txt, --metric-window 50, stan_cli @0cb5b7b
read-only), one callgrind job at a time. Usage:
  uv run python harness/w34/w34_callgrind.py run [stock|armB ...]
  uv run python harness/w34/w34_callgrind.py parse
"""
import json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / 'external/walnutpie/build_e27/examples/stan_cli'
OUT = ROOT / 'results/profile/w34'
VG = Path.home() / 'vginstall/bin'
SEED = 20260819
INIT = ROOT / 'inits_w25/hier_2pl/rep0/chain_0.txt'
ARMS = {
    'stock': ROOT / 'scratch/w34/stock_build/hier_2pl_model.so',
    'armB': ROOT / 'scratch/w34/armB_build/hier_2pl_model.so',
}


def sh(cmd, stdout=subprocess.DEVNULL, **kw):
    env = {k: v for k, v in os.environ.items() if k != 'LD_LIBRARY_PATH'}
    env['OMP_NUM_THREADS'] = '1'
    return subprocess.run([str(c) for c in cmd], env=env, stdout=stdout, **kw)


def run_arm(arm):
    od = OUT / arm
    od.mkdir(parents=True, exist_ok=True)
    cg = od / 'callgrind.out'
    if not cg.exists():
        r = sh([VG / 'valgrind', '--tool=callgrind', f'--callgrind-out-file={cg}', CLI,
                ARMS[arm], ROOT / 'data/hier_2pl.json',
                '--seed', SEED, '--init-file', INIT,
                '--warmup', 100, '--samples', 50,
                '--metric-window', '50',
                '--output', od / 'draws.csv'], timeout=14400)
        if r.returncode != 0:
            raise RuntimeError(f'{arm}: callgrind rc={r.returncode}')
        print(f'[w34] {arm}: callgrind done', flush=True)
    for flag, fn in [([], 'ann_exclusive.txt'), (['--inclusive=yes'], 'ann_inclusive.txt')]:
        f = od / fn
        if not (f.exists() and f.stat().st_size > 0):
            with f.open('w') as fh:
                sh([VG / 'callgrind_annotate'] + flag + [cg], stdout=fh)
    log = od / 'cli.log'
    if not log.exists():
        with log.open('w') as fh:
            sh([CLI, ARMS[arm], ROOT / 'data/hier_2pl.json',
                '--seed', SEED, '--init-file', INIT,
                '--warmup', 100, '--samples', 50, '--metric-window', '50',
                '--output', od / 'draws_native.csv'], stdout=fh, stderr=subprocess.STDOUT)


NUM = re.compile(r'^\s*([\d,]+)(?:\s+\([\s\d.,%]+\))?\s+(.*)$')


def parse_ann(path, max_lines=4000):
    lines = path.read_text(errors='replace').splitlines()
    total, funcs = None, []
    for line in lines[:max_lines]:
        m = re.match(r'^\s*([\d,]+)\s+PROGRAM TOTALS', line)
        if m:
            total = int(m.group(1).replace(',', ''))
            continue
        m = NUM.match(line)
        if m and ':' in m.group(2):
            try:
                funcs.append((int(m.group(1).replace(',', '')), m.group(2).strip()))
            except ValueError:
                pass
    return total, funcs


def parse_cli_log(path):
    txt = path.read_text(errors='replace')
    stanzas = [dict(zip(['total', 'logp_time', 'logp_frac', 'logp_calls', 'per_call'],
                        (float(m.group(i)) for i in range(1, 6))))
               for m in re.finditer(
                   r'total time: ([\d.eE+-]+)s?\s*\n'
                   r'logp_grad time: ([\d.eE+-]+)s?\s*\n'
                   r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
                   r'\s*logp_grad calls: (\d+)\s*\n'
                   r'\s*time per call: ([\d.eE+-]+)s\s*', txt)]
    return stanzas, txt.count('Error in logp_grad')


def parse():
    res = {}
    for arm in ARMS:
        od = OUT / arm
        te, fe = parse_ann(od / 'ann_exclusive.txt')
        ti, fi = parse_ann(od / 'ann_inclusive.txt')
        stanzas, errs = parse_cli_log(od / 'cli.log')
        res[arm] = dict(total=te, excl=fe[:80], incl=fi[:100],
                        cli_stanzas=stanzas, grad_errors=errs)
        print(f'[w34] {arm}: total={te:,}', flush=True)
    (OUT / 'w34_parsed.json').write_text(json.dumps(res, indent=1))
    print('->', OUT / 'w34_parsed.json')


if __name__ == '__main__':
    if sys.argv[1:2] == ['parse']:
        parse()
    else:
        for arm in (sys.argv[2:] or list(ARMS)):
            run_arm(arm)
