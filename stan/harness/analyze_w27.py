#!/usr/bin/env python
"""W-27 analysis: wall medians/ratios (default vs o3only), draw bit-identity."""
import csv, hashlib, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w27'
MODELS = ['blr', 'arma11', 'hier_2pl', 'kronecker_gp', 'diamonds']


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main():
    rows_all = {}
    for arm in ('default', 'o3only'):
        for m in MODELS:
            for rep in range(3):
                f = RUNS / arm / m / f'rep{rep}' / 'rows.csv'
                if not f.exists():
                    continue
                for r in csv.DictReader(f.open()):
                    rows_all.setdefault((arm, m), []).append(r)
    print('== per-model medians (3 reps; wall_batch_s = 4 chains in parallel, '
          'sampling_s / us_per_logp_grad = per-chain) ==')
    print(f'{"model":<14}{"wall def":>9}{"wall o3":>9}{"ratio":>7}'
          f'{"sampl def":>10}{"sampl o3":>10}{"ratio":>7}'
          f'{"us/call def":>12}{"us/call o3":>12}{"ratio":>7}')
    ratios = []
    for m in MODELS:
        if ('default', m) not in rows_all or ('o3only', m) not in rows_all:
            print(f'{m:<14} MISSING'); continue
        med = {}
        for arm in ('default', 'o3only'):
            rs = rows_all[(arm, m)]
            # wall is per rep (same for 4 chains) -> median over reps
            walls = {r['rep']: float(r['wall_batch_s']) for r in rs}
            med[arm] = dict(
                wall=st.median(walls.values()),
                samp=st.median(float(r['sampling_s']) for r in rs),
                us=st.median(float(r['us_per_logp_grad']) for r in rs))
        rw = med['o3only']['wall'] / med['default']['wall']
        rs_ = med['o3only']['samp'] / med['default']['samp']
        rc = med['o3only']['us'] / med['default']['us']
        ratios.append(rw)
        print(f'{m:<14}{med["default"]["wall"]:>9.1f}{med["o3only"]["wall"]:>9.1f}{rw:>7.3f}'
              f'{med["default"]["samp"]:>10.2f}{med["o3only"]["samp"]:>10.2f}{rs_:>7.3f}'
              f'{med["default"]["us"]:>12.1f}{med["o3only"]["us"]:>12.1f}{rc:>7.3f}')
    if ratios:
        gm = st.geometric_mean(ratios)
        print(f'geomean wall ratio (o3only/default): {gm:.3f}')
    # bit-identity of draws
    print('== draw bit-identity default vs o3only ==')
    nident = ntot = 0
    for m in MODELS:
        ident = True
        for rep in range(3):
            for c in range(4):
                a = RUNS / 'default' / m / f'rep{rep}' / f'chain_{c}.csv'
                b = RUNS / 'o3only' / m / f'rep{rep}' / f'chain_{c}.csv'
                if a.exists() and b.exists():
                    ntot += 1
                    if md5(a) != md5(b):
                        ident = False
        nident += sum(1 for rep in range(3) for c in range(4)
                      if (RUNS / 'default' / m / f'rep{rep}' / f'chain_{c}.csv').exists()
                      and (RUNS / 'o3only' / m / f'rep{rep}' / f'chain_{c}.csv').exists()
                      and md5(RUNS / 'default' / m / f'rep{rep}' / f'chain_{c}.csv')
                      == md5(RUNS / 'o3only' / m / f'rep{rep}' / f'chain_{c}.csv'))
        print(f'{m}: {"IDENTICAL" if ident else "DIFFER"}')
    print(f'total: {nident}/{ntot} chain CSVs bit-identical')


if __name__ == '__main__':
    main()
