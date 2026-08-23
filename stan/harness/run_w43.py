#!/usr/bin/env python3
"""W-43 gates: (a) default-path bit-identity canary for the
find_reasonable_step fix; (b) blr short-warmup pin-mitigation grid with
--step-init-heuristic (post-fix), vs the W-38-E2 base bands.

Runs are serialized single-chain CLI invocations (other agents share the
machine). Raw logs/CSVs under runs/w43/ (gitignored); parsed numbers to
results/w43_canary.json / results/w43_knob.json.
"""

import hashlib
import json
import os
import re
import subprocess
import sys

STAN = "/home/m0hawk/Documents/apin/stan"
CLI_POST = f"{STAN}/external/walnutpie_w43/build_w43/examples/stan_cli"
CLI_PRE = "/tmp/stan_cli_w43_prefix"  # same worktree, pre-fix build (saved)
RUNS = f"{STAN}/runs/w43/gates"
MODELS = {
    "arma11": ("model_arma11.so", "arma11.json"),
    "blr": ("model_blr.so", "blr.json"),
    "hier_2pl": ("model_hier_2pl.so", "hier_2pl.json"),
}


def run(cli, model, seed, warmup, samples, init_file, out_csv, extra, log):
    data = {"arma11": "arma11.json", "blr": "blr.json",
            "hier_2pl": "hier_2pl.json"}[model.removeprefix("model_").removesuffix(".so")]
    cmd = ["env", "-u", "LD_LIBRARY_PATH", "OMP_NUM_THREADS=1", cli,
           f"{STAN}/bs_models_threads/{model}", f"{STAN}/data/{data}",
           "--seed", str(seed), "--warmup", str(warmup),
           "--samples", str(samples)]
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


def main():
    os.makedirs(f"{RUNS}/canary", exist_ok=True)
    os.makedirs(f"{RUNS}/knob", exist_ok=True)

    # ---- gate (a): canary, default path, pre vs post binary ----
    canary = {}
    ok = 0
    for model, (so, _) in MODELS.items():
        for c in range(4):
            seed = 20260819 + c
            init = f"{STAN}/inits_w25/{model}/rep0/chain_{c}.txt"
            pre_csv = f"{RUNS}/canary/{model}_c{c}_pre.csv"
            post_csv = f"{RUNS}/canary/{model}_c{c}_post.csv"
            rc1 = run(CLI_PRE, so, seed, 1000, 1000, init, pre_csv, [],
                      f"{RUNS}/canary/{model}_c{c}_pre.log")
            rc2 = run(CLI_POST, so, seed, 1000, 1000, init, post_csv, [],
                      f"{RUNS}/canary/{model}_c{c}_post.log")
            same = rc1 == 0 and rc2 == 0 and md5(pre_csv) == md5(post_csv)
            ok += same
            canary[f"{model}_c{c}"] = dict(rc_pre=rc1, rc_post=rc2,
                                           md5_pre=md5(pre_csv),
                                           md5_post=md5(post_csv),
                                           identical=bool(same))
            print(f"[canary] {model} c{c}: {'IDENTICAL' if same else 'MISMATCH'}",
                  flush=True)
    canary["pass"] = f"{ok}/12"
    with open(f"{STAN}/results/w43_canary.json", "w") as fh:
        json.dump(canary, fh, indent=1)
    print(f"canary: {ok}/12", flush=True)

    # ---- gate (b): knob grid, blr, post binary ----
    grid = {}
    for warmup in (100, 400):
        for ini in ("pf", "def"):
            cells = []
            for rep in range(3):
                for c in range(4):
                    seed = 20260819 + 1000 * rep + c
                    init = (f"{STAN}/inits_w25/blr/rep{rep}/chain_{c}.txt"
                            if ini == "pf" else None)
                    csv = f"{RUNS}/knob/w{warmup}_{ini}_r{rep}_c{c}.csv"
                    log = f"{RUNS}/knob/w{warmup}_{ini}_r{rep}_c{c}.log"
                    rc = run(CLI_POST, "model_blr.so", seed, warmup, 1000,
                             init, csv, ["--step-init-heuristic"], log)
                    calls = None
                    heur = None
                    with open(log) as fh:
                        txt = fh.read()
                    m = re.search(r"Heuristic initial step size: ([\d.e+-]+)", txt)
                    if m:
                        heur = float(m.group(1))
                    m = re.search(r"logp_grad calls: (\d+)", txt)
                    if m:
                        calls = int(m.group(1))
                    cells.append(dict(rep=rep, c=c, seed=seed, rc=rc,
                                      heuristic_eps=heur, calls=calls))
                    print(f"[knob] w{warmup} {ini} r{rep} c{c}: rc={rc} "
                          f"eps={heur} calls={calls}", flush=True)
            grid[f"w{warmup}_{ini}"] = cells
    with open(f"{STAN}/results/w43_knob.json", "w") as fh:
        json.dump(grid, fh, indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
