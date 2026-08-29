# W-93 — combined posture (ridge guard × pf inits): composition CONFIRMED, super-additive

**Verdict: COMPOSE-candidate, all gates PASS. Aggregate geometric-mean
bulk ESS = 1094.9 vs 329.9 baseline = +231.9%** — far beyond either
parent alone (pf-only +84.7% [W-75], guard-only +57.4% [W-88]).
**30/30 cells complete — including the two historic abort cells.** The
full posture (pf inits + robustness stack + ridge guard) finishes every
cell on the suite. Date 2026-08-27.

## Per-model (median geoESS over 3 reps)

| model | base | pf only | guard only | BOTH | vs base |
|---|---:|---:|---:|---:|---:|
| radon_pp_nc | 2204.7 | 3877.0 | 2204.7 | 3877.0 | +75.8% |
| bym2_offset_only | 5.9 | 793.2 | 14.5 | 793.3 | **+13277%** |
| hier_2pl | 2673.1 | 2673.1 | 2673.1 | 2673.1 | 0 |
| diamonds | 60.3 | 234.3 | 802.1 | 507.5 | +742% |
| lsat_model | 3128.9 | 3128.9 | 3128.9 | 3128.9 | 0 |
| accel_gp | 42.6 | 31.9 | 45.0 | **3487.1** | **+8095%** |
| kronecker_gp | 369.7 | 285.7 | 369.7 | 285.7 | −22.7% |
| pilots | 426.4 | 353.3 | 685.4 | 521.3 | +22.2% |
| eight_schools_c | 237.0 | 270.7 | 399.3 | 270.7 | +14.2% |
| lotka_volterra | 1463.4 | 1348.6 | 1463.4 | 1348.6 | −7.8% |
| **AGGREGATE** | **329.9** | 609.5* | 519.6 | **1094.9** | **+231.9%** |

(*W-75 arm; W-74's +81.8% was the same posture pre-stack.)

## Gate outcomes

1. Aggregate ≥ +85% → **PASS** (+231.9%).
2. No model worse than BOTH parents by >10% → **PASS** (kronecker/lotka
   exactly equal their pf parent; diamonds 507.5 beats its pf parent
   though below guard-alone 802).
3. Unfired cells identical to pfall75 → **PASS** (md5 verified, e.g.
   hier_2pl rep1 = 680a4334…).

## Mechanism reading

- **Disjoint failure modes compose**: pf inits eliminate the INIT-side
  locks (bym2 back to 793 with no fire — the guard never triggers), the
  guard catches the SAMPLING-side residual locks (accel fires 3/3 under
  pf and jumps 32→3487; diamonds fires 3/3 → 507).
- accel_gp is the purest demonstration: neither fix alone reaches 50×;
  together +8095%.
- Overlap where pf fully prevents the lock (bym2: guard silent under
  pf vs 3/3 fires under normal inits) — redundancy is free (guard
  costs nothing when silent).
- kronecker/lotka deltas are the known pf-init posture effects, not
  guard harm (identical between pf-only and BOTH arms).
- diamonds BOTH (507) sits between parents — pf inits land chains
  closer together, so the guard has less dispersion to traverse at the
  same budget; still +742% over base.

## The shippable package (user decision)

pf-init workflow + robustness PRs #7/#8/#9/#10 + ridge guard PR #22
= +232% aggregate ESS on this suite, 30/30 completion, all safety
canaries green. Artifacts: runs/w93/gpf/**, results below; parents:
runs/w74, runs/w75, runs/w88.
