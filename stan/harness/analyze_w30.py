#!/usr/bin/env python
"""W-30 analysis: wall medians for the 4 execution-topology arms.

Arms: seq4 (4 sequential single-chain procs), par4 (4 parallel procs),
mc_serial / mc_threads (--chains 4 --fixed-warmup, serial vs threads
topology). Medians of 3 reps. Writes results/w30_wall.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w30'
MODELS = ['blr', 'arma11', 'hier_2pl', 'lsat_model', 'eight_schools_noncentered']
ARMS = ['seq4', 'par4', 'mc_serial', 'mc_threads']


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    walls, warm = {}, {}
    for model in MODELS:
        for arm in ARMS:
            vals, wvals = [], []
            for rep in range(reps):
                f = RUNS / arm / model / f'rep{rep}' / 'rows.csv'
                if not f.exists():
                    continue
                rows = list(pd.read_csv(f).to_dict('records'))
                vals.append(float(rows[0]['wall_batch_s']))
                wvals.append(float(rows[0]['warmup_s']) if
                             rows[0]['warmup_s'] == rows[0]['warmup_s'] else None)
            if vals:
                walls[f'{arm}/{model}'] = dict(
                    wall_med_s=round(float(np.median(vals)), 3),
                    per_rep=[round(v, 2) for v in vals])
                warm[f'{arm}/{model}'] = dict(
                    warm_med_s=(round(float(np.median([w for w in wvals
                                                       if w is not None])), 3)
                                if any(w is not None for w in wvals) else None))
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/w30_wall.json').write_text(
        json.dumps(dict(wall=walls, warmup=warm), indent=1))

    hdr = f"{'model':26s} " + ' '.join(f'{a:>10s}' for a in ARMS) + \
        '   thr/seq  thr/par  ser/seq'
    print(hdr)
    ratios = {'thr/seq': [], 'thr/par': [], 'ser/seq': []}
    for model in MODELS:
        row = [walls.get(f'{a}/{model}', {}).get('wall_med_s') for a in ARMS]
        def rat(i, j):
            return row[i] / row[j] if row[i] and row[j] else None
        r1, r2, r3 = rat(3, 0), rat(3, 1), rat(2, 0)
        for k, v in zip(ratios, (r1, r2, r3)):
            if v is not None:
                ratios[k].append(v)
        print(f"{model:26s} " + ' '.join(
            f"{v:10.2f}" if v else f"{'--':>10s}" for v in row) +
            '   ' + '  '.join(f"{v:6.2f}" if v else f"{'--':>6s}"
                              for v in (r1, r2, r3)))
    print('\ngeomean ratios:', {k: round(float(np.exp(np.mean(np.log(v)))), 3)
                                for k, v in ratios.items() if v})
    print('\nper-rep walls:')
    for model in MODELS:
        for arm in ARMS:
            e = walls.get(f'{arm}/{model}')
            if e:
                print(f"  {model:26s} {arm:10s} {e['per_rep']}")


if __name__ == '__main__':
    main()
