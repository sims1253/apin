#!/usr/bin/env python
"""W-37 separability analysis (pre-registered criterion, WORKLOG W-37).

From runs/w37/windows.json (per-chain window series), derive the signals
and evaluate the pre-registered gate statistics at window boundaries
k in {400, 450, 500, 550, 600}:

  mean_h(w) = sum_h / acc          (acc == 0 -> PIN window, mean_h None)
  ept(w)    = (fa+fw+bl+dl) / 50   (kernel evals per transition)

  D_h(k) = max_c |mean_h_c(k) - mean_h_c(k-2)|      [pin rule: inf]
  D_e(k) = max_c |ept_c(k) - ept_c(k-2)| / ept_c(k-2)
  S_h(k) = max_{c,c'} |mean_h_c(k) - mean_h_c'(k)|  [pin rule: inf]
  S_e(k) = max_c ept_c(k) / min_c ept_c(k) - 1      (corrected formula)

  D(k) = max(D_h/0.05, D_e/0.10, S_h/0.10, S_e/0.20)

Separability: exists k with max over EASY D(k) <= 0.5 AND min over
MARGINAL D(k) >= 2.0. Secondary reading swaps arma11 into MARGINAL.
Outputs results/w37_separability.json + a console summary table.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs/w37'
WINDOW = 50

EASY = ['blr', 'eight_schools_noncentered', 'arma11']
MARGINAL = ['hier_2pl', 'lsat_model']
KS = [400, 450, 500, 550, 600]
# Post-hoc (labeled): all evaluable boundaries for the "separates anywhere"
# scan that supports (or undermines) the permanent-closure claim.
KS_ALL = list(range(100, 1001, 50))

INF = float('inf')
UINT64 = 2 ** 64


def chain_signals(windows):
    """Map end-iteration -> (mean_h, ept, fw_share, bl_share, acc, macro).

    The measurement grid ran instrumentation commit 862381f, whose window
    records printed delta-of-deltas for sum_h/ge1 (record(k) = d(k) -
    d(k-1)); the TRUE per-window deltas are recovered EXACTLY by
    telescoping: d(k) = sum(record(1..k)) (pure integer identity, verified
    against the final phase histogram: blr_c0 recovered total sum_h = 803
    = 642*1 + 64*2 + 3*3 + 6*4). acc/fa/fw/bl/dl/exh were already true
    deltas in that revision.
    """
    sig = {}
    run_sum_h = 0
    run_ge1 = 0
    for w in windows:
        rec_sum_h = w['sum_h'] if w['sum_h'] < UINT64 // 2 else \
            w['sum_h'] - UINT64
        rec_ge1 = w['ge1'] if w['ge1'] < UINT64 // 2 else w['ge1'] - UINT64
        run_sum_h += rec_sum_h
        run_ge1 += rec_ge1
        total = w['fa'] + w['fw'] + w['bl'] + w['dl']
        mean_h = (run_sum_h / w['acc']) if w['acc'] > 0 else None
        sig[w['end']] = {
            'mean_h': mean_h,
            'ept': total / WINDOW,
            'fw_share': w['fw'] / total if total else None,
            'bl_share': w['bl'] / total if total else None,
            'ph1': (run_ge1 / w['acc']) if w['acc'] > 0 else None,
            'acc': w['acc'], 'macro': w['macro'], 'exh': w['exh'],
        }
    return sig


def model_stats(chains, ks=None):
    """chains: list of per-chain signal dicts. Return per-k stats."""
    out = {}
    for k in (ks if ks is not None else KS):
        if any(sig.get(k) is None or sig.get(k - 2 * WINDOW) is None
               for sig in chains):
            continue  # not evaluable at this k (missing window)
        dh, de = 0.0, 0.0
        for sig in chains:
            cur, prev = sig[k], sig[k - 2 * WINDOW]
            # T1 mean-h drift with pin rule
            if cur['mean_h'] is None or prev['mean_h'] is None:
                dh = INF
            else:
                dh = max(dh, abs(cur['mean_h'] - prev['mean_h']))
            # T2 ept drift (relative)
            de = max(de, abs(cur['ept'] - prev['ept']) /
                     max(prev['ept'], 1e-12))
        mean_hs = [sig[k]['mean_h'] for sig in chains]
        epts = [sig[k]['ept'] for sig in chains]
        # T3 spreads with pin rule
        sh = INF if any(m is None for m in mean_hs) else \
            max(mean_hs) - min(mean_hs)
        se = max(epts) / min(epts) - 1 if min(epts) > 0 else INF
        D = max(dh / 0.05, de / 0.10, sh / 0.10, se / 0.20)
        out[k] = {'D_h': None if dh == INF else dh,
                  'D_e': de,
                  'S_h': None if sh == INF else sh,
                  'S_e': se, 'D': None if D == INF else D,
                  'D_inf': D == INF,
                  'mean_h': [None if m is None else round(m, 3)
                             for m in mean_hs],
                  'ept': [round(e, 1) for e in epts]}
    return out or None


def main():
    data = json.loads((RUNS / 'windows.json').read_text())
    models = {}
    for tag, rec in data.items():
        if 'error' in rec:
            print(f'ERROR CELL {tag}: {rec["error"][:120]}')
            continue
        models.setdefault(rec['model'], {})[rec['chain']] = \
            chain_signals(rec['windows'])

    stats = {}
    for model, chains in models.items():
        stats[model] = model_stats([chains[c] for c in sorted(chains)])
    stats_all = {}
    for model, chains in models.items():
        stats_all[model] = model_stats([chains[c] for c in sorted(chains)],
                                       ks=KS_ALL)

    # console table
    print(f'{"model":26s} ' + ' '.join(f'{"D@" + str(k):>9s}' for k in KS))
    for model in EASY + MARGINAL + ['kronecker_gp']:
        if model not in stats or stats[model] is None:
            print(f'{model:26s} SHORT/ERROR')
            continue
        row = ' '.join(
            f'{"inf":>9s}' if stats[model][k]['D_inf']
            else f'{stats[model][k]["D"]:9.2f}' for k in KS)
        print(f'{model:26s} {row}')

    verdict = {'per_model': stats, 'primary': {}, 'secondary': {},
               'posthoc_all_k': {}}
    for label, easy, marg in [
            ('primary', EASY, MARGINAL),
            ('secondary_w21_classes', ['blr', 'eight_schools_noncentered'],
             ['hier_2pl', 'lsat_model', 'arma11'])]:
        sep = []
        for k in KS:
            easy_D = []
            marg_D = []
            ok = True
            for m in easy + marg:
                st = stats.get(m)
                if st is None or k not in st:
                    ok = False
                    break
                (easy_D if m in easy else marg_D).append(
                    INF if st[k]['D_inf'] else st[k]['D'])
            if not ok:
                continue
            passes = max(easy_D) <= 0.5 and min(marg_D) >= 2.0
            sep.append({'k': k, 'easy_max_D': max(easy_D),
                        'marginal_min_D': min(marg_D), 'separates': passes})
        verdict[label] = sep

    # POST-HOC (labeled, not pre-registered): does ANY k in 100..1000
    # separate the classes? Supports the closure claim if none does.
    for label, easy, marg in [
            ('primary', EASY, MARGINAL),
            ('secondary_w21_classes', ['blr', 'eight_schools_noncentered'],
             ['hier_2pl', 'lsat_model', 'arma11'])]:
        sep_all = []
        for k in KS_ALL:
            easy_D, marg_D, ok = [], [], True
            for m in easy + marg:
                st = stats_all.get(m)
                if st is None or k not in st:
                    ok = False
                    break
                (easy_D if m in easy else marg_D).append(
                    INF if st[k]['D_inf'] else st[k]['D'])
            if not ok:
                continue
            sep_all.append({'k': k, 'easy_max_D': max(easy_D),
                            'marginal_min_D': min(marg_D),
                            'separates': max(easy_D) <= 0.5 and
                                         min(marg_D) >= 2.0})
        verdict['posthoc_all_k'][label] = sep_all

    print('\nseparability by k (criterion: easy_max_D <= 0.5 AND '
          'marginal_min_D >= 2.0):')
    for label in ('primary', 'secondary_w21_classes'):
        print(f'  {label}:')
        for row in verdict[label]:
            e = 'inf' if row['easy_max_D'] == INF else f"{row['easy_max_D']:.2f}"
            m = 'inf' if row['marginal_min_D'] == INF else f"{row['marginal_min_D']:.2f}"
            print(f"    k={row['k']}: easy_max_D={e:>8s} "
                  f"marginal_min_D={m:>8s} separates={row['separates']}")

    print('\nPOST-HOC all-k scan (labeled; supports closure if empty):')
    for label, rows in verdict['posthoc_all_k'].items():
        n_sep = sum(r['separates'] for r in rows)
        n = len(rows)
        easies = [r['easy_max_D'] for r in rows if r['easy_max_D'] != INF]
        margs = [r['marginal_min_D'] for r in rows if r['marginal_min_D'] != INF]
        print(f'  {label}: {n_sep}/{n} ks separate; '
              f'easy_max_D range {min(easies):.2f}..{max(easies):.2f}, '
              f'marginal_min_D range {min(margs):.2f}..{max(margs):.2f}')

    # per-model series (report appendix): chain-avg mean_h / ept per window
    series = {}
    for model, chains in models.items():
        cl = [chains[c] for c in sorted(chains)]
        ends = sorted(cl[0].keys())
        series[model] = {end: {
            'mean_h_avg': (lambda v: None if not v else round(sum(v) / len(v), 3))(
                [s[end]['mean_h'] for s in cl if s[end]['mean_h'] is not None]),
            'ept_avg': round(sum(s[end]['ept'] for s in cl) / len(cl), 2),
            'ph1_avg': (lambda v: None if not v else round(sum(v) / len(v), 3))(
                [s[end]['ph1'] for s in cl if s[end]['ph1'] is not None]),
            'fw_avg': round(sum(s[end]['fw_share'] for s in cl) / len(cl), 3),
        } for end in ends}
    verdict['series'] = series

    (ROOT / 'results/w37_separability.json').write_text(
        json.dumps(verdict, indent=1))
    print('\nwrote results/w37_separability.json')


if __name__ == '__main__':
    sys.exit(main())
