#!/usr/bin/env python3
"""W-54 analysis: gate (b) blr knob-grid ESS/pin stats + gate (c) no-harm
bands (arviz, same procedure as analyze_w43.py: rank-normalized bulk/tail
ESS-min + max R-hat over parameters, medians of 3 reps; pinned chain = all
its draws identical). Run with: uv run --no-project python analyze_w54.py"""

import glob
import json
import os
import re

import arviz as az
import numpy as np
import pandas as pd

STAN = "/home/m0hawk/Documents/apin/stan"
RUNS = f"{STAN}/runs/w54"


def ess_stats(csvs):
    frames = [pd.read_csv(f) for f in csvs]
    uniq = [int(len(df.drop_duplicates()) == 1) for df in frames]
    vals = np.stack([fr.to_numpy() for fr in frames])
    ds = az.convert_to_dataset({"p": vals})
    eb = np.nan_to_num(az.ess(ds, method="bulk")["p"].values, nan=0.0)
    et = np.nan_to_num(az.ess(ds, method="tail")["p"].values, nan=0.0)
    rh = np.nan_to_num(az.rhat(ds)["p"].values, nan=9.0)
    return dict(ess_bulk_min=round(float(eb.min()), 1),
                ess_tail_min=round(float(et.min()), 1),
                rhat_max=round(float(rh.max()), 4),
                pinned_chains=sum(uniq))


def knob():
    out = {}
    arms = sorted({os.path.basename(p).split("_w")[0]
                   for p in glob.glob(f"{RUNS}/knob/*_w*_*.csv")})
    for arm in arms:
        cells = sorted({m.group(1) for p in
                        glob.glob(f"{RUNS}/knob/{arm}_w*.csv")
                        if (m := re.match(rf"{arm}_((w\d+)_(pf|def))",
                                          os.path.basename(p)))})
        for cell in cells:
            per = []
            heur_eps = []
            for rep in range(3):
                csvs = [f"{RUNS}/knob/{arm}_{cell}_r{rep}_c{c}.csv"
                        for c in range(4)]
                if not all(os.path.exists(f) for f in csvs):
                    continue
                st = ess_stats(csvs)
                per.append(st)
                log = (f"{RUNS}/knob/{arm}_{cell}_r{rep}_c0.log")
                if os.path.exists(log):
                    m = re.search(r"Heuristic initial step size: ([\d.e+-]+)",
                                  open(log).read())
                    if m:
                        heur_eps.append(float(m.group(1)))
            if not per:
                continue
            out[f"{arm}_{cell}"] = dict(
                n=len(per),
                ess_bulk_min_med=float(np.median(
                    [p["ess_bulk_min"] for p in per])),
                ess_tail_min_med=float(np.median(
                    [p["ess_tail_min"] for p in per])),
                rhat_max_med=float(np.median(
                    [p["rhat_max"] for p in per])),
                pinned_chains_tot=int(sum(p["pinned_chains"] for p in per)),
                per_rep=per)
            if heur_eps:
                out[f"{arm}_{cell}"]["heur_eps_min"] = min(heur_eps)
                out[f"{arm}_{cell}"]["heur_eps_max"] = max(heur_eps)
    with open(f"{STAN}/results/w54_knob_ess.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


def noharm():
    out = {}
    combos = sorted({os.path.basename(p).rsplit("_r", 1)[0]
                     for p in glob.glob(f"{RUNS}/noharm/*_r*_c*.csv")})
    for combo in combos:
        per = []
        for rep in range(3):
            csvs = [f"{RUNS}/noharm/{combo}_r{rep}_c{c}.csv" for c in range(4)]
            if not all(os.path.exists(f) for f in csvs):
                continue
            per.append(ess_stats(csvs))
        if not per:
            continue
        out[combo] = dict(
            n=len(per),
            ess_bulk_min_med=float(np.median([p["ess_bulk_min"] for p in per])),
            ess_tail_min_med=float(np.median([p["ess_tail_min"] for p in per])),
            rhat_max_med=float(np.median([p["rhat_max"] for p in per])),
            pinned_chains_tot=int(sum(p["pinned_chains"] for p in per)),
            per_rep=per)
    with open(f"{STAN}/results/w54_noharm_ess.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    import sys
    stage = sys.argv[1] if len(sys.argv) > 1 else "knob"
    dict(knob=knob, noharm=noharm)[stage]()
