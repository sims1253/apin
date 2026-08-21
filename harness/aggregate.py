#!/usr/bin/env python
"""Build the results table: per-config rows + per-variant/model aggregates."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'; ESS = ROOT / 'results/ess'; RESULTS = ROOT / 'results'

rows = []
for rows_csv in RUNS.glob('*/*/rep*/rows.csv'):
    d = rows_csv.parent
    if not (d / 'DONE').exists():
        continue
    variant, model, rep = rows_csv.parts[-4], rows_csv.parts[-3], rows_csv.parts[-2]
    df = pd.read_csv(rows_csv)
    for col in ('warmup_s', 'sampling_s', 'n_leapfrog_sampling', 'accept_mean',
                'stepsize_final', 'n_leapfrog_total', 'divergences', 'treedepth_hits'):
        if col not in df.columns:
            df[col] = float('nan')
    ess_path = ESS / f'{variant}__{model}__{rep}.json'
    e = json.loads(ess_path.read_text()) if ess_path.exists() else None
    r = dict(
        variant=variant, model=model, rep=int(rep.replace('rep', '')),
        wall_batch_s=df['wall_batch_s'].max(),
        sampler_s_per_chain=(df['warmup_s'].fillna(0) + df['sampling_s'].fillna(0)).mean(),
        warmup_s=df['warmup_s'].mean(), sampling_s=df['sampling_s'].mean(),
        n_leapfrog_total=int(df['n_leapfrog_total'].sum()),
        n_leapfrog_sampling=int(df['n_leapfrog_sampling'].sum()),
        divergences=int(df['divergences'].sum()),
        div_rate=df['divergences'].sum() / (4 * 1000),
        treedepth_hits=int(df['treedepth_hits'].sum()),
        td_rate=df['treedepth_hits'].sum() / (4 * 1000),
        accept_mean=df['accept_mean'].mean(),
        ess_bulk_min=e['ess_bulk_min'] if e else np.nan,
        ess_bulk_geomean=e['ess_bulk_geomean'] if e else np.nan,
        ess_tail_min=e['ess_tail_min'] if e else np.nan,
        rhat_max=e['rhat_max'] if e else np.nan,
        worst_param=(e['worst_params'][0] if e else None),
    )
    rows.append(r)

df = pd.DataFrame(rows)
for _c in ('ess_bulk_min','ess_bulk_geomean','ess_tail_min','rhat_max'):
    if _c in df.columns:
        df[_c] = pd.to_numeric(df[_c], errors='coerce')
if len(df):
    df['ess_per_sec'] = df['ess_bulk_min'] / df['wall_batch_s']
    # ess_per_grad must compare equal phases: n_leapfrog_total is
    # sampling-only for cmdstan (saved rows) but warmup+sampling for
    # walnutpie rows (see run_walnutpie.py), which biased walnutpie's
    # ratio ~2x down. Prefer the explicit sampling-phase column when
    # present; fall back to total only if missing.
    denom = df['n_leapfrog_sampling'] if 'n_leapfrog_sampling' in df else df['n_leapfrog_total']
    denom = denom.fillna(df['n_leapfrog_total']).replace(0, np.nan)
    df['ess_per_grad'] = df['ess_bulk_min'] / denom
    df.to_csv(RESULTS / 'table_per_config.csv', index=False)

    med = df.groupby(['variant', 'model']).median(numeric_only=True).reset_index()
    for need in ('rhat_max','ess_per_sec','ess_per_grad'):
        if need not in med.columns: med[need] = np.nan
    med.to_csv(RESULTS / 'table_per_model.csv', index=False)

    agg_rows = []
    for variant, g in med.groupby('variant'):
        gg = g.dropna(subset=['ess_per_sec'])
        agg_rows.append(dict(
            variant=variant, n_models=len(gg),
            geo_ess_per_sec=float(np.exp(np.mean(np.log(gg['ess_per_sec'])))) if len(gg) else np.nan,
            geo_wall=float(np.exp(np.mean(np.log(gg['wall_batch_s'])))) if len(gg) else np.nan,
            geo_ess_per_grad=float(np.exp(np.mean(np.log(gg['ess_per_grad'])))) if len(gg) else np.nan,
            total_div_rate=float(g['div_rate'].mean()),
            total_td_rate=float(g['td_rate'].mean()),
            n_configs_rhat_bad=int((g['rhat_max'] > 1.01).sum()),
        ))
    agg = pd.DataFrame(agg_rows)
    agg.to_csv(RESULTS / 'summary_variants.csv', index=False)
    print(agg.to_string(index=False))
