#!/usr/bin/env python3
"""W-40: compare two w40_unit cluster/wellsep outputs (or repro outputs) and
report per-section max relative gradient differences.
usage: cmp_grads.py <a.out> <b.out> [--detail]
Sections are '== <name> phi_x ==' headers followed by gA_<tag>[i] lines.
"""
import sys

def load(path):
    sec, out = None, {}
    for line in open(path):
        if line.startswith('== '):
            sec = line.strip('= \n')
            out[sec] = {}
        elif line.startswith('gA') and sec:
            tok, val = line.split()
            # tok like gA_ni[123]
            key = tok[:-1].rsplit('[', 1)
            out[sec][(key[0], int(key[1]))] = float(val)
    return out

a, b = load(sys.argv[1]), load(sys.argv[2])
detail = '--detail' in sys.argv
assert set(a) == set(b), (set(a) ^ set(b))
worst = []
for sec in a:
    assert set(a[sec]) == set(b[sec]), sec
    mx, mxk, mxabs = 0.0, None, 0.0
    for k in a[sec]:
        va, vb = a[sec][k], b[sec][k]
        if va != vb:
            d = abs(vb - va) / max(1.0, abs(va))
            if d > mx:
                mx, mxk = d, k
            mxabs = max(mxabs, abs(vb - va))
    print(f'{sec:32s} maxrel {mx:.3e}  (at {mxk})  maxabs {mxabs:.3e}  '
          f'{"IDENTICAL" if mx == 0 else ""}')
    worst.append((mx, sec, mxk))
if detail:
    print('\nworst sections:')
    for mx, sec, k in sorted(worst, reverse=True)[:6]:
        print(f'  {mx:.3e} {sec} {k}: {a[sec][k]!r} vs {b[sec][k]!r}')
