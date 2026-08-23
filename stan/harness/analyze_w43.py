#!/usr/bin/env python3
"""W-43 knob-grid ESS/pin analysis (arviz, same procedure as
analyze_w38e2.py: rank-normalized bulk/tail ESS-min + max R-hat over
parameters, medians of 3 reps; pinned chain = all its draws identical)."""

import glob
import json
import os

import arviz as az
import numpy as np
import pandas as pd

STAN = "/home/m0hawk/Documents/apin/stan"
RUNS = f"{STAN}/runs/w43/gates/knob"

out = {}
for arm in sorted(os.path.basename(d) for d in glob.glob(f"{RUNS}/w*_def")
                  + glob.glob(f"{RUNS}/w*_pf")):
    pass  # arms discovered from file prefixes below

arms = sorted({os.path.basename(p).rsplit("_r", 1)[0]
               for p in glob.glob(f"{RUNS}/w*_*_r*_c*.csv")})
for arm in arms:
    per = []
    for rep in range(3):
        frames = []
        uniq = []
        for c in range(4):
            f = f"{RUNS}/{arm}_r{rep}_c{c}.csv"
            df = pd.read_csv(f)
            frames.append(df)
            uniq.append(int(len(df.drop_duplicates()) == 1))
        big = pd.concat(frames, keys=range(4))
        vals = np.stack([fr.to_numpy() for fr in frames])  # (chain, draw, param)
        ds = az.convert_to_dataset(
            {"p": vals})  # one 3D variable, vectorized ESS (E2-validated)
        eb = np.nan_to_num(az.ess(ds, method="bulk")["p"].values, nan=0.0)
        et = np.nan_to_num(az.ess(ds, method="tail")["p"].values, nan=0.0)
        rh = np.nan_to_num(az.rhat(ds)["p"].values, nan=9.0)
        per.append(dict(
            ess_bulk_min=round(float(eb.min()), 1),
            ess_tail_min=round(float(et.min()), 1),
            rhat_max=round(float(rh.max()), 4),
            pinned_chains=sum(uniq)))
    out[arm] = dict(
        n=3,
        ess_bulk_min_med=float(np.median([p["ess_bulk_min"] for p in per])),
        ess_tail_min_med=float(np.median([p["ess_tail_min"] for p in per])),
        rhat_max_med=float(np.median([p["rhat_max"] for p in per])),
        pinned_chains_tot=int(sum(p["pinned_chains"] for p in per)),
        per_rep=per)

# attach call/heuristic summaries from the harness json
try:
    knob = json.load(open(f"{STAN}/results/w43_knob.json"))
    for arm, cells in knob.items():
        if arm in out:
            out[arm]["calls_med"] = float(np.median(
                [c["calls"] for c in cells if c["calls"]]))
            eps = [c["heuristic_eps"] for c in cells if c["heuristic_eps"]]
            out[arm]["heuristic_eps_min"] = min(eps) if eps else None
            out[arm]["heuristic_eps_max"] = max(eps) if eps else None
except FileNotFoundError:
    pass

with open(f"{STAN}/results/w43_ess.json", "w") as fh:
    json.dump(out, fh, indent=1)
print(json.dumps(out, indent=1))
