#!/usr/bin/env python
"""W-29: stan-math model-gradient hotspot atlas (callgrind on walnutpie stan_cli).

Runs ONE callgrind job at a time (valgrind is single-core; machine is shared),
then cg_annotate in three modes per model:
  exclusive (default), inclusive (--inclusive=yes), tree (--tree=both)
Raw dumps + annotate text land in results/profile/w29/<model>/.

Usage: uv run python harness/w29_callgrind.py run [model ...]   # callgrind + annotate
       uv run python harness/w29_callgrind.py parse             # parse annotate text -> w29_parsed.json
"""
import json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / 'external/walnutpie/build_e27/examples/stan_cli'
BS = ROOT / 'bs_models'
OUT = ROOT / 'results/profile/w29'
VG = Path.home() / 'vginstall/bin'
SEED = 20260819

# model -> (warmup, samples, init file)  [pre-registered in WORKLOG W-29]
MODELS = {
    'hier_2pl':     (100, 50, ROOT / 'inits_w25/hier_2pl/rep0/chain_0.txt'),
    'kronecker_gp': (100, 50, ROOT / 'inits_w27/kronecker_gp/rep0/chain_0.txt'),
    'gp_regr':      (50, 50, ROOT / 'inits_w27/gp_regr/rep0/chain_0.txt'),
    'accel_gp':     (50, 50, ROOT / 'inits_w27/accel_gp/rep0/chain_0.txt'),
    'diamonds':     (50, 50, ROOT / 'inits_w27/diamonds/rep0/chain_0.txt'),
}


def sh(cmd, stdout=subprocess.DEVNULL, **kw):
    env = {k: v for k, v in os.environ.items() if k != 'LD_LIBRARY_PATH'}
    env['OMP_NUM_THREADS'] = '1'
    return subprocess.run([str(c) for c in cmd], env=env, stdout=stdout, **kw)


def run_model(m):
    warmup, samples, init = MODELS[m]
    od = OUT / m
    od.mkdir(parents=True, exist_ok=True)
    cg = od / 'callgrind.out'
    log = od / 'cli.log'
    if not cg.exists():
        r = sh([VG / 'valgrind', '--tool=callgrind', f'--callgrind-out-file={cg}', CLI,
                BS / f'model_{m}.so', ROOT / f'data/{m}.json',
                '--seed', SEED, '--init-file', init,
                '--warmup', warmup, '--samples', samples,
                '--metric-window', '50',
                '--output', od / 'draws.csv'], timeout=3600)
        if r.returncode != 0:
            raise RuntimeError(f'{m}: callgrind rc={r.returncode}')
        print(f'[w29] {m}: callgrind done', flush=True)
    for mode, flag, fn in [('exclusive', [], 'ann_exclusive.txt'),
                           ('inclusive', ['--inclusive=yes'], 'ann_inclusive.txt'),
                           ('tree', ['--tree=both'], 'ann_tree.txt')]:
        f = od / fn
        if f.exists() and f.stat().st_size > 0:
            continue
        with f.open('w') as fh:
            sh([VG / 'callgrind_annotate'] + flag + [cg], stdout=fh)
        print(f'[w29] {m}: callgrind_annotate {mode} -> {fn}', flush=True)
    # also keep the native CLI log for call counts (cheap, no valgrind)
    if not log.exists():
        with log.open('w') as fh:
            sh([CLI, BS / f'model_{m}.so', ROOT / f'data/{m}.json',
                '--seed', SEED, '--init-file', init,
                '--warmup', warmup, '--samples', samples,
                '--metric-window', '50', '--output', od / 'draws_native.csv'],
               stdout=fh, stderr=subprocess.STDOUT)
    return


NUM = re.compile(r'^\s*([\d,]+)(?:\s+\([\s\d.,%]+\))?\s+(.*)$')


def parse_ann(path, max_lines=4000):
    """Return (total_Ir, [(Ir, 'file:function'), ...]) from a cg_annotate body."""
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
    errs = txt.count('Error in logp_grad')
    return stanzas, errs


def parse():
    res = {}
    for m in MODELS:
        od = OUT / m
        te, fe = parse_ann(od / 'ann_exclusive.txt')
        ti, fi = parse_ann(od / 'ann_inclusive.txt')
        stanzas, errs = parse_cli_log(od / 'cli.log')
        res[m] = dict(total=te, excl=fe[:60], incl=fi[:80],
                      cli_stanzas=stanzas, grad_errors=errs)
        print(f'[w29] {m}: total={te:,}', flush=True)
    (OUT / 'w29_parsed.json').write_text(json.dumps(res, indent=1))
    print('->', OUT / 'w29_parsed.json')


if __name__ == '__main__':
    if sys.argv[1:2] == ['parse']:
        parse()
    else:
        models = sys.argv[2:] or list(MODELS)
        for m in models:
            run_model(m)
