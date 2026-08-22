#!/usr/bin/env python
"""Rebuild runs/walnut/*/rep*/rows.csv from chain logs + draw CSVs with the
fixed stanza parser. wall_batch_s := max over chains (warmup+sample total),
the honest per-batch sampler wall under 4-way parallelism."""
import csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from run_walnutpie import parse_timing

ROOT = Path(__file__).resolve().parent.parent
for model_dir in sorted((ROOT/'runs/walnut').iterdir()):
    for rep_dir in sorted(model_dir.iterdir()):
        logs = sorted(rep_dir.glob('chain_*.log'))
        if not logs:
            continue
        rows = []
        for lg in logs:
            c = int(lg.stem.split('_')[1])
            blocks = parse_timing(lg.read_text())
            if len(blocks) < 2:
                print(f'skip {rep_dir}/chain_{c}: {len(blocks)} stanzas')
                continue
            warm_b, samp_b = blocks[0], blocks[1]
            draws_csv = rep_dir/f'chain_{c}.csv'
            n_rows = sum(1 for _ in open(draws_csv)) - 1 if draws_csv.exists() else 0
            rows.append(dict(model=model_dir.name, variant='walnut',
                             rep=int(rep_dir.name.replace('rep','')), chain=c,
                             warmup_s=warm_b['total'], sampling_s=samp_b['total'],
                             n_draws=n_rows,
                             n_leapfrog_total=int(warm_b['logp_calls']+samp_b['logp_calls']),
                             n_leapfrog_sampling=int(samp_b['logp_calls']),
                             divergences=-1, treedepth_hits=-1, stepsize_final=None,
                             accept_mean=None, lp_mean=None,
                             logp_frac_sampling=samp_b['logp_frac'],
                             us_per_logp_grad=samp_b['per_call']*1e6,
                             wall_batch_s=None, seed=None))
        wall = round(max(r['warmup_s']+r['sampling_s'] for r in rows), 3)
        for r in rows:
            r['wall_batch_s'] = wall
        out = rep_dir/'rows.csv'
        with out.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f'rebuilt {out}: wall={wall}')
