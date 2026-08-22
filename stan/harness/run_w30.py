#!/usr/bin/env python
"""W-30 runner: parallel multi-chain execution (event-driven controller +
serial/threads topology control).

Arms (all warmup=1000 draws=1000, --metric-window 50, pf inits from
inits_w25/, seeds 20260819+1000*rep (+c for per-chain arms); both mc arms
run --fixed-warmup so the controller executes the full budget and the
comparison isolates execution topology from early-exit noise):
  seq4      4 SEQUENTIAL single-chain CLI procs (wall = batch elapsed)
  par4      4 parallel single-chain procs (W-28's base configuration)
  mc_serial --chains 4 --chain-exec serial --fixed-warmup
  mc_threads --chains 4 --chain-exec threads --fixed-warmup

Also computes the gate-(b) md5 comparisons (mc_threads vs mc_serial chain
CSVs; bonus: mc vs seq4 chain CSVs, expected equal because W-25 seeded the
mc path to replicate the per-chain single-chain streams) and writes
results/w30_md5.json. Walls go into runs/w30/<arm>/<model>/rep<r>/rows.csv.
"""
import argparse, csv, hashlib, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w30'
STAN_CLI = ROOT / 'external/walnutpie/build/examples/stan_cli'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
MODELS = ['blr', 'arma11', 'hier_2pl', 'lsat_model', 'eight_schools_noncentered']
ARMS = ['seq4', 'par4', 'mc_serial', 'mc_threads']

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


def rows_from(timing_by_chain, model, arm, rep, wall, seed):
    rows = []
    for c in sorted(timing_by_chain):
        blocks = timing_by_chain[c]
        warm_b = blocks[0] if blocks else {}
        samp_b = blocks[1] if len(blocks) > 1 else {}
        rows.append(dict(
            model=model, variant=arm, rep=rep, chain=c,
            warmup_s=warm_b.get('total'), sampling_s=samp_b.get('total'),
            logp_calls_warm=int(warm_b.get('logp_calls', 0)),
            logp_calls_samp=int(samp_b.get('logp_calls', 0)),
            us_per_logp_warm=(warm_b.get('per_call', 0) * 1e6
                              if warm_b.get('per_call') else None),
            wall_batch_s=round(wall, 3), seed=seed))
    return rows


def write_rows(out_dir, rows):
    with (out_dir / 'rows.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def run_cell(model, rep, arm):
    out_dir = RUNS / arm / model / f'rep{rep}'
    if (out_dir / 'DONE').exists() and (out_dir / 'rows.csv').exists():
        return str(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    so = ROOT / 'bs_models_threads' / f'model_{model}.so'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    init_dir = ROOT / 'inits_w25' / model / f'rep{rep}'
    common = ['--warmup', str(WARMUP), '--samples', str(DRAWS),
              '--metric-window', '50']
    env = {**os.environ, 'OMP_NUM_THREADS': '1'}
    t0 = time.time()
    if arm in ('mc_serial', 'mc_threads'):
        exec_mode = 'serial' if arm == 'mc_serial' else 'threads'
        cmd = [str(STAN_CLI), str(so), data, '--seed', str(seed),
               '--chains', str(CHAINS), '--chain-exec', exec_mode,
               '--fixed-warmup',
               '--init-file', str(init_dir / 'chain_{c}.txt'),
               '--output', str(out_dir / 'chain_{c}.csv')] + common
        log = out_dir / 'mc.log'
        with log.open('w') as lf:
            p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env)
        if p.returncode != 0:
            raise RuntimeError(f'{arm}/{model}/rep{rep} rc={p.returncode}')
        text = log.read_text()
        em = re.search(r'controller exit_iter=(\d+) early_exit=(\d+)', text)
        if not em or em.group(1) != str(WARMUP) or em.group(2) != '0':
            raise RuntimeError(
                f'{arm}/{model}/rep{rep}: warmup not fixed-length: '
                f'{em.group(0) if em else "no controller line"}')
        rows = rows_from(parse_mc(text), model, arm, rep, time.time() - t0, seed)
    else:
        procs = []
        for c in range(CHAINS):
            csv_path = out_dir / f'chain_{c}.csv'
            cmd = [str(STAN_CLI), str(so), data, '--seed', str(seed + c),
                   '--init-file', str(init_dir / f'chain_{c}.txt'),
                   '--output', str(csv_path)] + common
            lf = (out_dir / f'chain_{c}.log').open('w')
            pr = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                  env=env)
            procs.append((c, pr, lf))
            if arm == 'seq4':
                pr.wait(); lf.close()
                if pr.returncode != 0:
                    raise RuntimeError(f'{arm}/{model}/rep{rep} c{c} rc')
        timing = {}
        for c, pr, lf in procs:
            pr.wait(); lf.close()
            if pr.returncode != 0:
                raise RuntimeError(f'{arm}/{model}/rep{rep} c{c} rc')
            timing[c] = parse_sc((out_dir / f'chain_{c}.log').read_text())
        rows = rows_from(timing, model, arm, rep, time.time() - t0, seed)
    write_rows(out_dir, rows)
    return str(out_dir)


def md5_checks(reps):
    out = {}
    for model in MODELS:
        for rep in range(reps):
            key = f'{model}/rep{rep}'
            rec = out.setdefault(key, {})
            for arm in ARMS:
                d = RUNS / arm / model / f'rep{rep}'
                if (d / 'DONE').exists():
                    rec[arm] = {f'chain_{c}': md5(d / f'chain_{c}.csv')
                                for c in range(CHAINS)}
            if 'mc_serial' in rec and 'mc_threads' in rec:
                rec['gate_b_equal'] = rec['mc_serial'] == rec['mc_threads']
            if 'seq4' in rec and 'mc_threads' in rec:
                rec['bonus_mc_eq_singlechain'] = \
                    rec['seq4'] == rec['mc_threads']
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/w30_md5.json').write_text(json.dumps(out, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=','.join(MODELS))
    ap.add_argument('--arms', default=','.join(ARMS))
    ap.add_argument('--md5-only', action='store_true')
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    if not args.md5_only:
        for rep in range(args.reps):
            for m in [x for x in args.models.split(',') if x]:
                for arm in [x for x in args.arms.split(',') if x]:
                    t0 = time.time()
                    try:
                        d = run_cell(m, rep, arm)
                        rows = list(csv.DictReader((Path(d) / 'rows.csv').open()))
                        print(f'[w30] {arm}/{m}/rep{rep}: '
                              f'wall={rows[0]["wall_batch_s"]}s '
                              f'({time.time()-t0:.1f}s)', flush=True)
                    except Exception as ex:
                        print(f'[w30] {arm}/{m}/rep{rep}: FAILED {ex}',
                              flush=True)
    checks = md5_checks(args.reps)
    gb = [k for k, v in checks.items() if v.get('gate_b_equal') is False]
    bn = [k for k, v in checks.items() if v.get('bonus_mc_eq_singlechain')]
    print(f'[w30] gate b (mc serial==threads): '
          f'{"ALL EQUAL" if not gb else f"FAIL {gb}"}', flush=True)
    print(f'[w30] bonus mc==single-chain holds for {len(bn)}/{len(checks)} '
          f'cells', flush=True)
    print('W30 GRID DONE', flush=True)


if __name__ == '__main__':
    main()
