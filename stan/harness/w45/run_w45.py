#!/usr/bin/env python
"""W-45 runner: data-subsampled warmup transplant.

Arms (all warmup=1000 iters on the warmup model, draws=1000 on the
full-data model, 4 chains as 4 SEQUENTIAL single-chain invocations,
3 reps, seeds 20260819+1000*rep+c, pf inits inits_w25/ per the W-36
assignment, CLI-default configs, full-data .so from bs_models_threads/):

  base      stan_cli (build_w36exp, read-only) full-data warmup+sampling
  toolbase  w45_run full  (CLI-clone fidelity + source of base frozen state)
  v1_aXX    w45_run warmup on the alpha-subsample .so, then w45_run sample
            on the full-data .so with the transplanted state (pure)
  v2_aXX    same shared warmup state + --retune-step (find_reasonable_step
            on the full-data model with the transplanted mass)

Wall: external per-process clock; a transplant cell's wall = phase1+phase2
external walls. Internal stanzas parsed for calls/warmup-vs-sampling split.

Outputs under runs/w45/: <arm>/<model>/rep<r>/{chain_<c>.csv,chain_<c>.log,
rows.csv,DONE}; frozen states under runs/w45/state/{base,aXX}/<model>/...
Resumable (DONE markers). Serialized single-chain everywhere.
"""
import argparse, csv, hashlib, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / 'runs' / 'w45'
CLI = ROOT / 'external/walnutpie/build_w36exp/examples/stan_cli'
TOOL = ROOT / 'scratch/w45/bin/w45_run'
WARMUP, DRAWS, CHAINS, REPS = 1000, 1000, 4, 3
BASE_SEED = 20260819
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr']
ALPHAS = ['25', '10']
ARMS = (['base', 'toolbase']
        + [f'v1_a{a}' for a in ALPHAS] + [f'v2_a{a}' for a in ALPHAS])

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


def init_file(model, rep, c):
    return ROOT / 'inits_w25' / model / f'rep{rep}' / f'chain_{c}.txt'


def full_so(model):
    return ROOT / 'bs_models_threads' / f'model_{model}.so'


def sub_so(model, a):
    return ROOT / f'scratch/w45/build_{model}_a{a}' / f'{model}_model.so'


def sub_data(model, a):
    return ROOT / 'scratch/w45/data' / f'{model}_a{a}.json'


def run_cmd(cmd, log_path):
    env = {**os.environ, 'OMP_NUM_THREADS': '1'}
    t0 = time.time()
    with log_path.open('w') as lf:
        p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env)
    return p.returncode, time.time() - t0


def write_rows(out_dir, rows):
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')


def done(out_dir):
    return (out_dir / 'DONE').exists() and (out_dir / 'rows.csv').exists()


# ---------------------------------------------------------------- arms --
def arm_base(model, rep, tool=False):
    out_dir = RUNS / ('toolbase' if tool else 'base') / model / f'rep{rep}'
    if done(out_dir):
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = BASE_SEED + 1000 * rep
    rows = []
    for c in range(CHAINS):
        csv_path = out_dir / f'chain_{c}.csv'
        if tool:
            state_path = (RUNS / 'state' / 'base' / model / f'rep{rep}'
                          / f'chain_{c}.state')
            state_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [str(TOOL), 'full', str(full_so(model)),
                   str(ROOT / f'data/{model}.json'),
                   '--seed', str(seed + c), '--init-file',
                   str(init_file(model, rep, c)), '--warmup', str(WARMUP),
                   '--samples', str(DRAWS), '--output', str(csv_path),
                   '--dump-state', str(state_path)]
        else:
            cmd = [str(CLI), str(full_so(model)),
                   str(ROOT / f'data/{model}.json'),
                   '--seed', str(seed + c), '--init-file',
                   str(init_file(model, rep, c)), '--output', str(csv_path),
                   '--warmup', str(WARMUP), '--samples', str(DRAWS)]
        rc, wall = run_cmd(cmd, out_dir / f'chain_{c}.log')
        if rc != 0:
            raise RuntimeError(f'{out_dir.name} {model} rep{rep} c{c} rc={rc}')
        blocks = parse_sc((out_dir / f'chain_{c}.log').read_text())
        rows.append(dict(
            model=model, arm='toolbase' if tool else 'base', rep=rep, chain=c,
            warmup_s=blocks[0]['total'] if blocks else None,
            sampling_s=blocks[1]['total'] if len(blocks) > 1 else None,
            logp_calls_warm=int(blocks[0]['logp_calls']) if blocks else 0,
            logp_calls_samp=(int(blocks[1]['logp_calls'])
                             if len(blocks) > 1 else 0),
            wall_ext_s=round(wall, 3),
            csv_md5=md5(csv_path) if csv_path.exists() else None))
    write_rows(out_dir, rows)


def arm_transplant(model, rep, variant, a):
    """variant in {'v1','v2'}: shared subsample warmup state + sample."""
    out_dir = RUNS / f'{variant}_a{a}' / model / f'rep{rep}'
    if done(out_dir):
        return
    seed = BASE_SEED + 1000 * rep
    # phase 1: subsample warmup (shared across v1/v2)
    state_dir = RUNS / 'state' / f'a{a}' / model / f'rep{rep}'
    warm_log = state_dir / f'chain_warm.log'
    state_paths = [state_dir / f'chain_{c}.state' for c in range(CHAINS)]
    if not all(sp.exists() for sp in state_paths):
        state_dir.mkdir(parents=True, exist_ok=True)
        warm_walls = {}
        for c in range(CHAINS):
            sp = state_paths[c]
            if sp.exists():
                continue
            cmd = [str(TOOL), 'warmup', str(sub_so(model, a)),
                   str(sub_data(model, a)), '--seed', str(seed + c),
                   '--init-file', str(init_file(model, rep, c)),
                   '--warmup', str(WARMUP), '--dump-state', str(sp)]
            rc, wall = run_cmd(cmd, state_dir / f'chain_{c}.log')
            if rc != 0:
                raise RuntimeError(f'warmup {model} a{a} rep{rep} c{c} rc={rc}')
            warm_walls[str(c)] = wall
        warm_log.write_text('ok')
        (state_dir / 'warm_walls.json').write_text(json.dumps(warm_walls))
    else:
        state_paths = [state_dir / f'chain_{c}.state' for c in range(CHAINS)]
    warm_walls = {int(k): v for k, v in
                  json.loads((state_dir / 'warm_walls.json').read_text()
                             ).items()}
    # phase 2: full-data sampling with the transplanted state
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in range(CHAINS):
        csv_path = out_dir / f'chain_{c}.csv'
        cmd = [str(TOOL), 'sample', str(full_so(model)),
               str(ROOT / f'data/{model}.json'), '--seed', str(seed + c),
               '--load-state', str(state_paths[c]), '--samples', str(DRAWS),
               '--output', str(csv_path)]
        if variant == 'v2':
            cmd.append('--retune-step')
        rc, samp_wall = run_cmd(cmd, out_dir / f'chain_{c}.log')
        if rc != 0:
            raise RuntimeError(f'{variant}_a{a} {model} rep{rep} c{c} rc={rc}')
        blocks = parse_sc((out_dir / f'chain_{c}.log').read_text())
        st = parse_state(state_paths[c])
        rows.append(dict(
            model=model, arm=f'{variant}_a{a}', rep=rep, chain=c,
            warmup_s=None, sampling_s=blocks[0]['total'] if blocks else None,
            logp_calls_warm=0, logp_calls_samp=(int(blocks[0]['logp_calls'])
                                                if blocks else 0),
            wall_ext_s=round(warm_walls.get(c, 0.0) + samp_wall, 3),
            wall_warm_s=round(warm_walls.get(c, 0.0), 3),
            wall_samp_s=round(samp_wall, 3),
            t_step=st['step'], t_min_micro=st['min_micro'],
            csv_md5=md5(csv_path) if csv_path.exists() else None))
    write_rows(out_dir, rows)


def parse_state(path):
    txt = {}
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if parts[0] in ('dim', 'step', 'min_micro', 'lp'):
            txt[parts[0]] = float(parts[1])
    return {'step': txt['step'], 'min_micro': int(txt['min_micro']),
            'lp': txt['lp'], 'dim': int(txt['dim'])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', nargs='*', default=MODELS)
    ap.add_argument('--reps', type=int, default=REPS)
    ap.add_argument('--arms', nargs='*', default=None,
                    help='subset of: base toolbase v1 v2 warm')
    args = ap.parse_args()
    arms = args.arms or ['base', 'toolbase', 'v1', 'v2']
    for model in args.models:
        for rep in range(args.reps):
            if 'base' in arms:
                arm_base(model, rep)
            if 'toolbase' in arms:
                arm_base(model, rep, tool=True)
            for variant in ('v1', 'v2'):
                if variant in arms:
                    for a in ALPHAS:
                        arm_transplant(model, rep, variant, a)
            print(f'[w45] {model} rep{rep} complete', flush=True)


if __name__ == '__main__':
    main()
