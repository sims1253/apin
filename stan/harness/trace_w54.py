#!/usr/bin/env python3
"""W-54 gate (d): parse WALNUTPIE_PIN_TRACE logs from runs/w54/trace/ and
emit per-arm summaries (escape iteration, metric trajectory, boundary
tables) to results/w54_trace.json + printed boundary tables."""

import glob
import json
import os
import re

STAN = "/home/m0hawk/Documents/apin/stan"

FIELDS = ["it", "lp", "step", "invm_geo", "invm_min", "invm_max", "pos_l2",
          "pos_max", "moved", "macro", "attempts", "evals", "znorm", "alpha",
          "dlogp", "mindh", "tolpass", "hacc", "ladrej", "exhaust"]


def parse(path):
    rows = []
    for line in open(path):
        if "[pin-trace]" not in line:
            continue
        toks = re.findall(r"(\w+)=(-?(?:inf|nan|[\d.e+-]+))", line)
        d = {k: v for k, v in toks}
        if "it" not in d:
            continue
        row = {}
        for f in FIELDS:
            v = d.get(f, "nan")
            row[f] = float("inf") if v == "inf" else (
                float("-inf") if v == "-inf" else (
                    float("nan") if v == "nan" else float(v)))
        rows.append(row)
    return rows


def summarize(rows):
    out = {}
    moved = [r for r in rows if r["moved"] == 1]
    esc = moved[0]["it"] if moved else None
    out["n_iters"] = len(rows)
    out["escape_iter"] = esc
    if esc is not None:
        i = next(i for i, r in enumerate(rows) if r["it"] == esc)
        out["boundary"] = rows[max(0, i - 3):i + 3]
    # metric trajectory checkpoints
    for it in (0, 10, 50, 74, 75, 76, 100, 150, 199, 200, 201, 300, 500,
               999):
        r = next((r for r in rows if r["it"] == it), None)
        if r:
            out[f"it{it}"] = {k: r[k] for k in
                              ("step", "invm_geo", "alpha", "dlogp", "mindh",
                               "moved", "evals")}
    # alpha-underflow census (engine check)
    finite = [r for r in rows if r["alpha"] >= 0.0]
    out["alpha_zero_iters"] = sum(1 for r in finite if r["alpha"] == 0.0)
    out["alpha_pos_iters"] = sum(1 for r in finite if r["alpha"] > 0.0)
    return out


def main():
    out = {}
    for path in sorted(glob.glob(f"{STAN}/runs/w54/trace/*.log")):
        name = os.path.basename(path)[:-4]
        rows = parse(path)
        if rows:
            out[name] = summarize(rows)
    with open(f"{STAN}/results/w54_trace.json", "w") as fh:
        json.dump(out, fh, indent=1)
    for name, s in out.items():
        print(f"== {name}: escape={s['escape_iter']} "
              f"alpha0/alpha+ = {s['alpha_zero_iters']}/{s['alpha_pos_iters']}")
        for k, v in s.items():
            if k.startswith("it") and isinstance(v, dict):
                print(f"  {k}: step={v['step']:.4g} invm={v['invm_geo']:.4g} "
                      f"alpha={v['alpha']:.3g} dlogp={v['dlogp']:.4g} "
                      f"mindh={v['mindh']:.4g} moved={v['moved']:.0f}")
        if "boundary" in s:
            print("  boundary:")
            for r in s["boundary"]:
                print(f"   it={r['it']:.0f} step={r['step']:.5g} "
                      f"invm={r['invm_geo']:.6g} alpha={r['alpha']:.3g} "
                      f"dlogp={r['dlogp']:.4g} mindh={r['mindh']:.4g} "
                      f"moved={r['moved']:.0f} hacc={r['hacc']:.0f} "
                      f"evals={r['evals']:.0f}")


if __name__ == "__main__":
    main()
