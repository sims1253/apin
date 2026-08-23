#!/usr/bin/env python
"""W-36 runner: end-to-end session headline benchmark.

stock walnutpie @ 3eddfc4 (worktree build_w36stock) vs exp tip
exp/safe-adapt-defaults @ 43b6435 (worktree build_w36exp), both at CLI
DEFAULTS (only --warmup 1000 --samples 1000 passed explicitly; metric
window stays default/off), 10-model pathfinder grid, 4 chains, 3 reps,
seeds 20260819+1000*rep+c.

Arms:
  stock_seq  STOCK binary, 4 SEQUENTIAL single-chain invocations (pre-session
             status quo workflow; wall = batch elapsed)
  exp_par    EXP binary, --chains 4 --chain-exec threads, defaults otherwise
             (gate: controller exit_iter=1000 early_exit=0 in every run)
  exp_seq    EXP binary, 4 sequential single-chain invocations (optional arm:
             isolates W-23 endpoint-threading from W-30 parallelism)

Inits: inits_w25 (pf) for hier_2pl/lsat_model, inits_w36 (deterministic
normal) for the other 8 — identical files across all arms.
Outputs: runs/w36/<arm>/<model>/rep<r>/{chain_<c>.csv,logs,rows.csv,DONE}.
"""
import argparse, csv, hashlib, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w36'
EXP_CLI = ROOT / 'external/walnutpie/build_w36exp/examples/stan_cli'
STOCK_CLI = ROOT / 'external/walnutpie_stock_w36/build_w36stock/examples/stan_cli'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
MODELS = ['radon_partially_pooled_noncentered', 'bym2_offset_only', 'hier_2pl',
          'diamonds', 'lsat_model', 'accel_gp', 'kronecker_gp', 'pilots',
          'eight_schools_centered', 'lotka_volterra']
PF_INIT_MODELS = {'hier_2pl', 'lsat_model'}
ARMS = ['stock_seq', 'exp_par', 'exp_seq']

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


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def init_dir_for(model, rep):
    sub = 'inits_w25' if model in PF_INIT_MODELS else 'inits_w36'
    return ROOT / sub / model / f'rep{rep}'


def cli_for(arm):
    return STOCK_CLI if arm == 'stock_seq' else EXP_CLI


def rows_from(timing_by_chain, model, arm, rep, wall, seed, exit_info):
    rows = []
    for c in sorted(timing_by_chain):
        blocks = timing_by_chain[c]
        warm_b = blocks[0] if blocks else {}
        samp_b = blocks[1] if len(blocks) > 1 else {}
        csv_path = RUNS / arm / model / f'rep{rep}' / f'chain_{c}.csv'
        rows.append(dict(
            model=model, variant=arm, rep=rep, chain=c,
            warmup_s=warm_b.get('total'), sampling_s=samp_b.get('total'),
            logp_calls_warm=int(warm_b.get('logp_calls', 0)),
            logp_calls_samp=int(samp_b.get('logp_calls', 0)),
            us_per_logp_warm=(warm_b.get('per_call', 0) * 1e6
                              if warm_b.get('per_call') else None),
            us_per_logp_samp=(samp_b.get('per_call', 0) * 1e6
                              if samp_b.get('per_call') else None),
            wall_batch_s=round(wall, 3), seed=seed,
            exit_iter=exit_info[0], early_exit=exit_info[1],
            csv_md5=md5(csv_path) if csv_path.exists() else None))
    return rows


def write_rows(out_dir, rows):
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')


def run_cell(model, rep, arm):
    out_dir = RUNS / arm / model / f'rep{rep}'
    if (out_dir / 'DONE').exists() and (out_dir / 'rows.csv').exists():
        return str(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    so = ROOT / 'bs_models_threads' / f'model_{model}.so'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    init_dir = init_dir_for(model, rep)
    env = {**os.environ, 'OMP_NUM_THREADS': '1'}
    t0 = time.time()
    if arm == 'exp_par':
        cmd = [str(EXP_CLI), str(so), data, '--seed', str(seed),
               '--chains', str(CHAINS), '--chain-exec', 'threads',
               '--init-file', str(init_dir / 'chain_{c}.txt'),
               '--output', str(out_dir / 'chain_{c}.csv'),
               '--warmup', str(WARMUP), '--samples', str(DRAWS)]
        log = out_dir / 'mc.log'
        with log.open('w') as lf:
            p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env)
        if p.returncode != 0:
            raise RuntimeError(f'{arm}/{model}/rep{rep} rc={p.returncode}')
        text = log.read_text()
        em = re.search(r'controller exit_iter=(\d+) early_exit=(\d+)', text)
        if not em or em.group(1) != str(WARMUP) or em.group(2) != '0':
            raise RuntimeError(
                f'{arm}/{model}/rep{rep}: early-exit posture wrong: '
                f'{em.group(0) if em else "no controller line"}')
        exit_info = (int(em.group(1)), int(em.group(2)))
        timing = parse_mc(text)
    else:
        cli = cli_for(arm)
        timing = {}
        for c in range(CHAINS):
            csv_path = out_dir / f'chain_{c}.csv'
            cmd = [str(cli), str(so), data, '--seed', str(seed + c),
                   '--init-file', str(init_dir / f'chain_{c}.txt'),
                   '--output', str(csv_path),
                   '--warmup', str(WARMUP), '--samples', str(DRAWS)]
            lf_path = out_dir / f'chain_{c}.log'
            with lf_path.open('w') as lf:
                p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                   env=env)
            if p.returncode != 0:
                raise RuntimeError(f'{arm}/{model}/rep{rep} c{c} rc={p.returncode}')
            timing[c] = parse_sc(lf_path.read_text())
        exit_info = (None, None)
    rows = rows_from(timing, model, arm, rep, time.time() - t0, seed, exit_info)
    write_rows(out_dir, rows)
    return str(out_dir)


def md5_report(reps, models, arms):
    out = {}
    for model in models:
        for rep in range(reps):
            rec = {}
            for arm in arms:
                d = RUNS / arm / model / f'rep{rep}'
                if (d / 'DONE').exists():
                    rec[arm] = {f'chain_{c}': md5(d / f'chain_{c}.csv')
                                for c in range(CHAINS)}
            if 'stock_seq' in rec and 'exp_seq' in rec:
                rec['canary_stock_vs_exp_seq'] = rec['stock_seq'] == rec['exp_seq']
            if 'stock_seq' in rec and 'exp_par' in rec:
                rec['bonus_stock_vs_exp_par'] = rec['stock_seq'] == rec['exp_par']
            out[f'{model}/rep{rep}'] = rec
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/w36_md5.json').write_text(json.dumps(out, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=','.join(MODELS))
    ap.add_argument('--arms', default='stock_seq,exp_par')
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    models = [m for m in args.models.split(',') if m]
    arms = [a for a in args.arms.split(',') if a]
    for rep in range(args.reps):
        for m in models:
            for arm in arms:
                t0 = time.time()
                try:
                    d = run_cell(m, rep, arm)
                    rows = list(csv.DictReader((Path(d) / 'rows.csv').open()))
                    r0 = rows[0]
                    print(f'[w36] {arm}/{m}/rep{rep}: wall={r0["wall_batch_s"]}s '
                          f'exit={r0.get("exit_iter")}/{r0.get("early_exit")} '
                          f'({time.time()-t0:.1f}s)', flush=True)
                except Exception as ex:
                    print(f'[w36] {arm}/{m}/rep{rep}: FAILED {ex}', flush=True)
    md5_report(args.reps, models, arms)
    print('W36 GRID DONE', flush=True)


if __name__ == '__main__':
    main()
