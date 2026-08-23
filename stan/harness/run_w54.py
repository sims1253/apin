#!/usr/bin/env python3
"""W-54 gates harness (stages, serialized single-chain CLI invocations):
  canary  — gate (a): default-path bit-identity, base vs post binary
            (arma11/blr/hier_2pl x 4 chains, 1000+1000, seeds 20260819+c,
            rep0 pf inits)
  knob    — gate (b): blr pin battery, w100/w400 x pf/def x 3 reps x 4
            chains, seeds 20260819+1000*rep+c, knob arms below
  noharm  — gate (c): hier_2pl + lsat_model w1000 1000 samples, base vs
            knob arms, same seed protocol
  trace   — gate (d): WALNUTPIE_PIN_TRACE=1 blr 1-chain w1000 runs

Raw logs/CSVs under runs/w54/ (gitignored); parsed numbers to
results/w54_*.json by analyze_w54.py.
"""

import hashlib
import json
import os
import subprocess
import sys

STAN = "/home/m0hawk/Documents/apin/stan"
CLI = f"{STAN}/external/walnutpie_w54/build_w54/examples/stan_cli"
# Knob-isolating reference: the SAME worktree built at b657198 (both
# cherry-picks, BEFORE the W-54 knob commit). The full-binary base
# (/tmp/stan_cli_w54_base, exp/safe-adapt-defaults @ 43b6435) is passed
# as CLI_BASE when given: the pin-trace hooks perturb hot-loop codegen
# (last-ulp |dH| -> escape-time shift), so the 43b6435 comparison is
# reported separately, not as the knob gate.
import sys
CLI_BASE = sys.argv[2] if len(sys.argv) > 2 else \
    "/tmp/w54_preknob/build_bisect/examples/stan_cli"
RUNS = f"{STAN}/runs/w54"
DATA = {"arma11": "arma11.json", "blr": "blr.json",
        "hier_2pl": "hier_2pl.json", "lsat_model": "lsat_model.json"}

# gate (b) arms: name -> extra CLI args
KNOB_ARMS = {
    "base": [],
    "heur": ["--step-init-heuristic"],
    "a75": ["--mass-init-buffer", "75"],
    "a50": ["--mass-init-buffer", "50"],
    "a100": ["--mass-init-buffer", "100"],
    "b1e10": ["--grad-clip-scale", "1e10"],
    "b1e8": ["--grad-clip-scale", "1e8"],
    "b1e6": ["--grad-clip-scale", "1e6"],
    "a75_heur": ["--mass-init-buffer", "75", "--step-init-heuristic"],
    "b1e6_heur": ["--grad-clip-scale", "1e6", "--step-init-heuristic"],
    "b1e10_heur": ["--grad-clip-scale", "1e10", "--step-init-heuristic"],
}
# cells per arm for gate (b): (warmup, init) — full grid for primary arms,
# w100-only for probes/combos
KNOB_CELLS = {
    "base": [(100, "pf"), (400, "pf"), (100, "def"), (400, "def")],
    "heur": [(100, "pf"), (400, "pf"), (100, "def"), (400, "def")],
    "a75": [(100, "pf"), (400, "pf"), (100, "def"), (400, "def")],
    "a50": [(100, "pf"), (100, "def")],
    "a100": [(100, "pf"), (100, "def")],
    "b1e10": [(100, "pf"), (400, "pf"), (100, "def"), (400, "def")],
    "b1e8": [(100, "pf"), (100, "def")],
    "b1e6": [(100, "pf"), (100, "def")],
    "a75_heur": [(100, "pf"), (400, "pf"), (100, "def")],
    "b1e6_heur": [(100, "pf"), (100, "def")],
    "b1e10_heur": [(100, "pf"), (100, "def")],
}
NOHARM_ARMS = ["base", "a75", "b1e10", "b1e6"]


def run(cli, model, seed, warmup, samples, init_file, out_csv, extra, log,
        pin_trace=False):
    data = DATA[model]
    cmd = ["env", "-u", "LD_LIBRARY_PATH", "OMP_NUM_THREADS=1", cli,
           f"{STAN}/bs_models_threads/model_{model}.so", f"{STAN}/data/{data}",
           "--seed", str(seed), "--warmup", str(warmup),
           "--samples", str(samples)]
    if pin_trace:
        cmd.insert(3, "WALNUTPIE_PIN_TRACE=1")
    if init_file:
        cmd += ["--init-file", init_file]
    cmd += extra
    if out_csv:
        cmd += ["--output", out_csv]
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                            cwd=STAN).returncode
    return rc


def md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def canary():
    import hashlib as _h
    tag = _h.md5(CLI_BASE.encode()).hexdigest()[:6]
    out_json = f"{STAN}/results/w54_canary_{tag}.json"
    os.makedirs(f"{RUNS}/canary_{tag}", exist_ok=True)
    out = {"cli_base": CLI_BASE}
    ok = 0
    for model in ("arma11", "blr", "hier_2pl"):
        for c in range(4):
            seed = 20260819 + c
            init = f"{STAN}/inits_w25/{model}/rep0/chain_{c}.txt"
            base_csv = f"{RUNS}/canary_{tag}/{model}_c{c}_base.csv"
            post_csv = f"{RUNS}/canary_{tag}/{model}_c{c}_post.csv"
            rc1 = run(CLI_BASE, model, seed, 1000, 1000, init, base_csv, [],
                      f"{RUNS}/canary_{tag}/{model}_c{c}_base.log")
            rc2 = run(CLI, model, seed, 1000, 1000, init, post_csv, [],
                      f"{RUNS}/canary_{tag}/{model}_c{c}_post.log")
            same = rc1 == 0 and rc2 == 0 and md5(base_csv) == md5(post_csv)
            ok += same
            out[f"{model}_c{c}"] = dict(rc_base=rc1, rc_post=rc2,
                                        md5_base=md5(base_csv),
                                        md5_post=md5(post_csv),
                                        identical=bool(same))
            print(f"[canary:{tag}] {model} c{c}: "
                  f"{'IDENTICAL' if same else 'MISMATCH'}", flush=True)
    out["pass"] = f"{ok}/12"
    with open(out_json, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"canary({tag}): {ok}/12 -> {out_json}", flush=True)


def knob():
    os.makedirs(f"{RUNS}/knob", exist_ok=True)
    meta = {}
    for arm, cells in KNOB_CELLS.items():
        for (warmup, ini) in cells:
            for rep in range(3):
                for c in range(4):
                    seed = 20260819 + 1000 * rep + c
                    init = (f"{STAN}/inits_w25/blr/rep{rep}/chain_{c}.txt"
                            if ini == "pf" else None)
                    csv = f"{RUNS}/knob/{arm}_w{warmup}_{ini}_r{rep}_c{c}.csv"
                    log = (f"{RUNS}/knob/{arm}_w{warmup}_{ini}_r{rep}_c{c}"
                           f".log")
                    if os.path.exists(csv) and os.path.getsize(csv) > 0:
                        continue  # resumable
                    rc = run(CLI, "blr", seed, warmup, 1000, init, csv,
                             KNOB_ARMS[arm], log)
                    print(f"[knob] {arm} w{warmup} {ini} r{rep} c{c}: "
                          f"rc={rc}", flush=True)
                    meta[f"{arm}_w{warmup}_{ini}_r{rep}_c{c}"] = rc
    with open(f"{RUNS}/knob/_rc.json", "w") as fh:
        json.dump(meta, fh, indent=1)


def noharm():
    os.makedirs(f"{RUNS}/noharm", exist_ok=True)
    for model in ("hier_2pl", "lsat_model"):
        for arm in NOHARM_ARMS:
            extra = [] if arm == "base" else KNOB_ARMS[arm]
            for rep in range(3):
                for c in range(4):
                    seed = 20260819 + 1000 * rep + c
                    init = f"{STAN}/inits_w25/{model}/rep{rep}/chain_{c}.txt"
                    csv = f"{RUNS}/noharm/{model}_{arm}_r{rep}_c{c}.csv"
                    log = f"{RUNS}/noharm/{model}_{arm}_r{rep}_c{c}.log"
                    if os.path.exists(csv) and os.path.getsize(csv) > 0:
                        continue
                    rc = run(CLI, model, seed, 1000, 1000, init, csv, extra,
                             log)
                    print(f"[noharm] {model} {arm} r{rep} c{c}: rc={rc}",
                          flush=True)


def trace():
    os.makedirs(f"{RUNS}/trace", exist_ok=True)
    # knob off vs A75 vs B1e6, blr default init, seed 20260819, w1000
    arms = {
        "off": [],
        "a75": ["--mass-init-buffer", "75"],
        "b1e6": ["--grad-clip-scale", "1e6"],
        "a75_heur": ["--mass-init-buffer", "75", "--step-init-heuristic"],
        "heur": ["--step-init-heuristic"],
    }
    for arm, extra in arms.items():
        log = f"{RUNS}/trace/blr_def_{arm}.log"
        rc = run(CLI, "blr", 20260819, 1000, 100, None, None, extra, log,
                 pin_trace=True)
        print(f"[trace] def {arm}: rc={rc}", flush=True)
    for arm in ("off", "a75", "heur", "a75_heur"):
        log = f"{RUNS}/trace/blr_pf_{arm}.log"
        init = f"{STAN}/inits_w25/blr/rep0/chain_0.txt"
        rc = run(CLI, "blr", 20260819, 1000, 100, init, None,
                 arms[arm], log, pin_trace=True)
        print(f"[trace] pf {arm}: rc={rc}", flush=True)


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "canary"
    dict(canary=canary, knob=knob, noharm=noharm, trace=trace)[stage]()
