#!/usr/bin/env python
"""Pre-registered Pathfinder ablations (see WORKLOG): pf_full, pf_w200.

Per model: 1 pathfinder run (num_paths=4 default) -> PSIS draws CSV; chain c
init = random draw (rng: rep/chain-seeded), unflattened to Stan JSON of the
PARAMETERS block only. Then standard 4-chain cmdstan sampling (seeds per
CORE_SET protocol), warmup per variant. Wall includes pathfinder time.
"""
import argparse, csv, json, os, random, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'
WARMUP_DEFAULT, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
MAX_DEPTH = 10

VARIANTS = {'pf_full': 1000, 'pf_w200': 200}

DECL_RE = re.compile(r'''
 ^\s*
 (array\s*\[.*?\]\s*)?
 (real|int|complex|vector|row_vector|matrix|tuple|
  cov_matrix|corr_matrix|cholesky_factor_corr|cholesky_factor_cov|
  simplex|ordered|positive_ordered|unit_vector)
 (\s*<[^>]*>)?            # constraints
 (\s*\[[^\]]*\])*
 \s+[A-Za-z_]\w*
 (\s*\[[^\]]*\])*
 (\s*=[^;]*)?
 \s*;$
''', re.X | re.S)

def find_block(text, header_re):
    mm = re.search(header_re, text, re.M)
    if not mm: return None
    brace = text.index('{', mm.start())
    depth = 0; i = brace; in_str=False; in_cmt=None
    while i < len(text):
        ch = text[i]; nxt = text[i+1] if i+1 < len(text) else ''
        if in_cmt:
            if in_cmt == '//' and ch == '\n': in_cmt = None
            elif in_cmt == '/*' and ch == '*' and nxt == '/': in_cmt = None; i += 1
        elif in_str:
            if ch == '"': in_str = False
        elif ch == '/' and nxt == '/': in_cmt = '//'; i += 1
        elif ch == '/' and nxt == '*': in_cmt = '/*'; i += 1
        elif ch == '"': in_str = True
        elif ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: return text[brace+1:i]
        i += 1
    return None

def param_names(stan_path):
    body = find_block(stan_path.read_text(), r'^parameters\s*\{')
    names = []
    for stmt in body.split(';'):
        s = re.sub(r'//[^\n]*', '', stmt).strip()
        if not s: continue
        if DECL_RE.match(s + ';'):
            t = re.sub(r'<[^>]*>', ' ', s)          # strip constraints (may contain '=')
            t = t.split('=')[0]                      # drop initializer
            t = re.sub(r'\[[^\]]*\]', ' ', t)     # drop dims
            ids = re.findall(r'[A-Za-z_]\w*', t)
            if len(ids) >= 2:                        # type + name
                names.append(ids[-1])
    return names

def unflatten(flat, params):
    """flat: {colname: value}; keep only cols whose top-level name is in params."""
    out = {}
    for col, val in flat.items():
        parts = col.split('.')
        if parts[0] not in params: continue
        idxs = [int(p) for p in parts[1:]] if len(parts) > 1 else []
        if not idxs:
            out[col] = val
            continue
        # walk/create nested lists
        cur = out.setdefault(parts[0], None)
        node = out
        key = parts[0]
        for depth, ix in enumerate(idxs):
            if node[key] is None:
                node[key] = [None] * max(ix, 1) if depth == 0 else node[key]
            while len(node[key]) < ix:
                node[key].append(None)
            nxt_key = ix - 1
            if depth == len(idxs) - 1:
                node[key][nxt_key] = val
            else:
                if node[key][nxt_key] is None:
                    node[key][nxt_key] = []
                node = {None: node[key]}
                # simpler: manual recursion below
                break
        if len(idxs) > 1:
            # handle multi-dim via helper
            pass
    # redo cleanly with recursive setter
    def set_deep(container, idxs, val):
        ix = idxs[0] - 1
        while len(container) <= ix:
            container.append(None)
        if len(idxs) == 1:
            container[ix] = val
        else:
            if container[ix] is None:
                container[ix] = []
            set_deep(container[ix], idxs[1:], val)
    out = {}
    for col, val in flat.items():
        parts = col.split('.')
        if parts[0] not in params: continue
        if len(parts) == 1:
            out[parts[0]] = val
        else:
            arr = out.setdefault(parts[0], [])
            set_deep(arr, [int(p) for p in parts[1:]], val)
    return out

def run_pathfinder(model):
    od = RUNS / 'pathfinder' / model
    od.mkdir(parents=True, exist_ok=True)
    csv_path = od / 'pf.csv'
    if csv_path.exists():
        return 0.0
    exe = ROOT / 'build' / f'{model}__default' / 'model'
    t0 = time.time()
    r = subprocess.run([str(exe), 'data', f'file={ROOT}/data/{model}.json',
                        'random', f'seed={BASE_SEED}',
                        'output', f'file={csv_path}', 'method=pathfinder'],
                       capture_output=True, text=True)
    if r.returncode != 0 or not csv_path.exists():
        raise RuntimeError(f'pathfinder failed: {r.stderr[-300:]}')
    return time.time() - t0

def read_pf_draws(model):
    csv_path = RUNS / 'pathfinder' / model / 'pf.csv'
    lines = [l for l in csv_path.read_text().splitlines() if not l.startswith('#')]
    hdr = lines[0].split(',')
    return hdr, [dict(zip(hdr, l.split(','))) for l in lines[1:]]

def elapsed_from_csv(path):
    txt = path.read_text().splitlines()
    warm = samp = None
    for i, line in enumerate(txt):
        m = re.search(r'Elapsed Time: ([\d.eE+-]+) seconds \(Warm-up\)', line)
        if m: warm = float(m.group(1))
        m2 = re.match(r'#\s*([\d.eE+-]+) seconds \(Sampling\)', line)
        if m2 and warm is not None and samp is None: samp = float(m2.group(1))
    hdr_idx = next(i for i, l in enumerate(txt) if l and not l.startswith('#') and ',' in l)
    header = txt[hdr_idx].split(',')
    rows = [l.split(',') for l in txt[hdr_idx+1:] if l and not l.startswith('#') and ',' in l]
    def col(name):
        if name not in header: return []
        j = header.index(name); out = []
        for r in rows:
            if len(r) == len(header):
                try: out.append(float(r[j]))
                except ValueError: pass
        return out
    leap = col('n_leapfrog__'); div = col('divergent__'); td = col('treedepth__')
    acc = col('accept_stat__'); step = col('stepsize__'); lp = col('lp__')
    return dict(warmup_s=warm, sampling_s=samp, n_draws=len(rows),
                n_leapfrog_total=int(sum(leap)),
                divergences=int(sum(1 for v in div if v == 1)),
                treedepth_hits=int(sum(1 for v in td if v >= MAX_DEPTH)),
                stepsize_final=step[-1] if step else None,
                accept_mean=sum(acc)/len(acc) if acc else None,
                lp_mean=sum(lp)/len(lp) if lp else None)

def run_variant(model, variant, rep, pf_secs):
    warmup = VARIANTS[variant]
    out_dir = RUNS / variant / model / f'rep{rep}'
    rows_path = out_dir / 'rows.csv'
    if (out_dir / 'DONE').exists() and rows_path.exists():
        return list(csv.DictReader(rows_path.open()))
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'build' / f'{model}__default' / 'model'
    data = str(ROOT / f'data/{model}.json')
    seed = BASE_SEED + 1000 * rep
    hdr, draws = read_pf_draws(model)
    params = param_names(ROOT / f'models/{model}.stan')
    procs = []
    t0 = time.time()
    for c in range(CHAINS):
        rng = random.Random(f'{seed}-{c}')
        draw = draws[rng.randrange(len(draws))]
        flat = {k: float(v) for k, v in draw.items() if k not in ('lp_approx__', 'lp__', 'path__')}
        init = unflatten(flat, params)
        init_path = out_dir / f'init_{c}.json'
        init_path.write_text(json.dumps(init))
        csv_path = out_dir / f'chain_{c}.csv'
        cmd = [str(exe), f'id={c+1}', 'data', f'file={data}', 'random', f'seed={seed}',
               f'init={init_path}', 'output', f'file={csv_path}',
               'method=sample', f'num_warmup={warmup}', f'num_samples={DRAWS}', 'save_warmup=0']
        procs.append((c, csv_path, subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)))
    for c, _, p in procs:
        err = p.communicate()[1]
        if p.returncode != 0:
            raise RuntimeError(f'chain {c} rc={p.returncode}: {err.decode()[:300]}')
    wall = time.time() - t0 + pf_secs
    rows = []
    for c, csv_path, _ in procs:
        d = elapsed_from_csv(csv_path)
        d.update(model=model, variant=variant, rep=rep, chain=c,
                 wall_batch_s=round(wall, 3), seed=seed, pf_secs=round(pf_secs, 3))
        rows.append(d)
    with rows_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    (out_dir / 'DONE').write_text('ok')
    return rows

MODELS = ['radon_partially_pooled_noncentered', 'bym2_offset_only', 'hier_2pl',
          'diamonds', 'lsat_model', 'accel_gp', 'kronecker_gp', 'pilots',
          'eight_schools_centered', 'lotka_volterra']

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--models', default=','.join(MODELS))
    args = ap.parse_args()
    os.environ['OMP_NUM_THREADS'] = '1'
    models = args.models.split(',')
    pf_time = {}
    for m in models:
        try:
            pf_time[m] = run_pathfinder(m)
            print(f'[pf] {m}: pathfinder {pf_time[m]:.1f}s', flush=True)
        except Exception as e:
            print(f'[pf] {m}: FAILED {e}', flush=True)
            continue
        for variant in VARIANTS:
            for rep in range(args.reps):
                try:
                    rows = run_variant(m, variant, rep, pf_time[m])
                    r0 = rows[0]
                    print(f"[run] {variant}/{m}/rep{rep}: wall={r0['wall_batch_s']:.1f}s "
                          f"warm={r0['warmup_s']} samp={r0['sampling_s']} "
                          f"div={sum(int(r['divergences']) for r in rows)}", flush=True)
                except Exception as ex:
                    print(f'[run] {variant}/{m}/rep{rep}: FAILED {ex}', flush=True)
    print('PATHFINDER GRID DONE', flush=True)

if __name__ == '__main__':
    main()
