# W-82: guarded min-micro-2 — reactive pin-detection + MM1 restart (the safe-by-construction path)

Pre-registration: WORKLOG "W-82 PRE-REGISTRATION (before any code)" (guarded
min-micro-2 entry). Binary: `external/walnutpie_mm2guard/build_mg/examples/stan_cli`,
branch `robustness/mm2-guard` = dev/init-robustness (3eddfc4) + W-82 guard
7a5cf1c + NaN-adapter-guard cherry-pick ef524a5 (= 6ba0798). Feature status
before this campaign (gated, recorded by the build session): default/MM1
canaries byte-identical incl. the post-cherry-pick state (W-81 SoA canary
lineage, md5 fe7c57…), a gpcm guarded recovery md5-exact to the MM1 run,
225/225 ctest. This campaign reconfirms binary-equivalence independently:
fresh A0 vs the W-80b pf A0 grids is md5-EQUAL on 36/36 chains
(gpcm/election88/hier_gp 12/12 each), and A0/gp_regr rep0_c0 md5-matches the
W-63 A0 grid (cf45d…).

## Protocol

9 models x 3 arms x 3 reps x 4 chains = 324 runs, all complete (324/324 rc=0,
3F+0P reps in every cell). w1000 s1000, `--metric-window 50`, single chain per
process, seeds 20260819+1000*rep+chain, `env -u LD_LIBRARY_PATH`,
OMP_NUM_THREADS=1, pf inits per source (w63 manifest init_dirs for the six
CORE_SET/manifest models; scratch/w80/inits for the three posteriordb models).
Arms: A0 = min-micro default (fresh SAME-BINARY baseline — W-63/W-79/W-80
grids NOT reused, per pre-reg arm-consistency), MM2 = `--min-micro-steps 2`,
GMD = MM2 + `--min-micro-guard` (defaults probe 50 / min-unique 25 =
unique/probe < 0.5). Machine: 3 workers against ~3 foreign load; one mid-run
kill (driver SIGTERM) exercised the resume path — 3 in-flight jobs rerun
cleanly; total ~92 min. Driver/analyzer: scratch/w82/{driver.py,analyze_w82.py}
(w79 conventions; runs scratch/w82/runs/<arm>/<model>/rep<r>_c<chain>.{csv,log}).

## 9x3 grid (rep medians; grads = sampling stanza; wall = all stanzas incl. discarded guard attempts)

| model | arm | ESS_min | grads/draw | wall_s | ESS/s | rhat>1.02 | pinned | guard fires | logp_grad errors |
|---|---|---|---|---|---|---|---|---|---|
| election88_full | A0 | 8.0 | 89.4 | 467.1 | 0.017 | 102 | 0 | – | 0 |
| election88_full | MM2 | 16.8 | 122.0 | 696.7 | 0.024 | 31 | 0 | – | 0 |
| election88_full | GMD | 16.8 | 122.0 | 672.2 | 0.025 | 31 | 0 | 0 | 0 |
| gpcm_latent_reg_irt | A0 | 537.4 | 82.7 | 411.0 | 1.308 | 0 | 0 | – | 10594 |
| gpcm_latent_reg_irt | MM2 | 2.1 | 221.0 | 793.3 | 0.003 | 550 | 7 | – | 401773 |
| gpcm_latent_reg_irt | GMD | 658.6 | 112.2 | 693.4 | 0.950 | 0 | 0 | 7 | 241039 |
| hier_2pl | A0 | 493.4 | 67.4 | 189.0 | 2.610 | 0 | 0 | – | 728 |
| hier_2pl | MM2 | 1556.6 | 130.6 | 336.7 | 4.622 | 0 | 0 | – | 6023 |
| hier_2pl | GMD | 1556.6 | 130.6 | 337.6 | 4.611 | 0 | 0 | 0 | 6023 |
| lsat_model | A0 | 940.8 | 73.5 | 31.0 | 30.397 | 0 | 0 | – | 0 |
| lsat_model | MM2 | 1196.5 | 166.6 | 60.7 | 19.699 | 0 | 0 | – | 0 |
| lsat_model | GMD | 1196.5 | 166.6 | 60.1 | 19.897 | 0 | 0 | 0 | 0 |
| hierarchical_gp | A0 | 4.1 | 96.9 | 18.1 | 0.229 | 1143 | 0 | – | 15244 |
| hierarchical_gp | MM2 | 35.7 | 211.6 | 35.7 | 1.000 | 222 | 0 | – | 54669 |
| hierarchical_gp | GMD | 35.7 | 211.6 | 36.2 | 0.986 | 222 | 0 | 0 | 54669 |
| dogs_hierarchical | A0 | 1592.1 | 22.8 | 2.8 | 577.1 | 0 | 0 | – | 0 |
| dogs_hierarchical | MM2 | 2637.7 | 23.3 | 3.1 | 858.2 | 0 | 0 | – | 34 |
| dogs_hierarchical | GMD | 2637.7 | 23.3 | 3.1 | 858.1 | 0 | 0 | 0 | 34 |
| gp_regr | A0 | 2261.6 | 26.0 | 0.3 | 6872.9 | 0 | 0 | – | 18 |
| gp_regr | MM2 | 3909.3 | 29.3 | 0.4 | 10282.2 | 0 | 0 | – | 290 |
| gp_regr | GMD | 3909.3 | 29.3 | 0.4 | 10337.0 | 0 | 0 | 0 | 290 |
| blr | A0 | 346.6 | 92.6 | 0.5 | 724.0 | 0 | 0 | – | 28552 |
| blr | MM2 | 491.4 | 157.2 | 1.1 | 462.3 | 0 | 0 | – | 106892 |
| blr | GMD | 491.4 | 157.2 | 1.1 | 463.0 | 0 | 0 | 0 | 106892 |
| eight_schools_centered | A0 | 103.5 | 83.4 | 0.1 | 920.9 | 1 | 0 | – | 0 |
| eight_schools_centered | MM2 | 79.6 | 114.2 | 0.1 | 546.2 | 1 | 0 | – | 93 |
| eight_schools_centered | GMD | 79.6 | 114.2 | 0.1 | 540.8 | 1 | 0 | 0 | 93 |

## Ratios vs A0 (ESS/grad on sampling-stanza grads)

| model | MM2 ESSr | GMD ESSr | MM2 E/grad | GMD E/grad | GMD/MM2 ESS | MM2 wall | GMD wall |
|---|---|---|---|---|---|---|---|
| election88_full | 2.097 | 2.097 | 1.537 | 1.537 | 1.000 | 1.492 | 1.439 |
| gpcm_latent_reg_irt | 0.004 | 1.226 | 0.001 | 0.903 | 310.5 | 1.930 | 1.687 |
| hier_2pl | 3.155 | 3.155 | 1.628 | 1.628 | 1.000 | 1.782 | 1.786 |
| lsat_model | 1.272 | 1.272 | 0.561 | 0.561 | 1.000 | 1.962 | 1.943 |
| hierarchical_gp | 8.602 | 8.602 | 3.939 | 3.939 | 1.000 | 1.970 | 1.998 |
| dogs_hierarchical | 1.657 | 1.657 | 1.619 | 1.619 | 1.000 | 1.114 | 1.114 |
| gp_regr | 1.729 | 1.729 | 1.532 | 1.532 | 1.000 | 1.155 | 1.149 |
| blr | 1.417 | 1.417 | 0.835 | 0.835 | 1.000 | 2.220 | 2.216 |
| eight_schools_centered | 0.769 | 0.769 | 0.561 | 0.561 | 1.000 | 1.296 | 1.309 |

The fresh grid reproduces the known MM2 taxonomy: catastrophic gpcm
(ESS/grad 0.001, 7/12 chains pinned, 402k logp_grad errors), benefits
hier_gp 3.94 / hier_2pl 1.63 / dogs 1.62 / gp_regr 1.53 / election88 1.54,
mild harm lsat 0.56 / 8sch_c 0.56 / blr 0.84 — all consistent with W-79/
W-80b labels.

## Guard-fire census (the gate evidence)

- gpcm GMD: **7 fires** — r0c0, r0c1, r0c2, r1c1, r1c2, r1c3, r2c0, each
  "1/50 unique parameter rows (< 25)". This is EXACTLY the W-80b MM2 pinned
  set (7/12) and exactly this grid's MM2 pin set (fire set == pin set).
- All other 8 models x 12 GMD chains: **0 fires**.
- Probe-uniqueness margin (MM2 arm, unique rows in first 50 draws):
  min/median = 43/49 election88, 48/50 hier_2pl, 47/49 lsat, 50/50 hier_gp,
  50/50 dogs, 46/47 gp_regr, 40/48 blr, 34/42 8sch_c — vs 1/1 on the pinned
  gpcm chains. Separation 1 vs >=34 against a threshold of 25: no borderline
  cell anywhere near the trip point.
- md5 identities (mechanism proofs):
  - all 7 firing GMD chains are md5-IDENTICAL to the fresh A0 same-seed
    chains (the in-process restart is exactly an MM1 run), 0 mismatches;
  - all 96 silent GMD chains (8 models x 12) are md5-IDENTICAL to their MM2
    counterparts (the guard's storage probe is read-only; draw stream
    unperturbed), 0 mismatches — which is why GMD == MM2 exactly
    (ESS ratio 1.000, same errors, same grads) wherever the guard stays
    silent;
  - fresh A0 vs W-80b pf A0: md5-equal 36/36 (binary-equivalence canary).

## Wall overhead (the wasted-probe cost)

GMD/MM2 per-model wall ratios: 0.874 (gpcm), 0.965 (election88), 0.990–1.014
(all others) — i.e. the guard costs nothing measurable on silent chains
(one uniqueness scan of 50 stored rows) and is overall ~12% CHEAPER than raw
MM2 on the catastrophic model: aborting a pinned attempt after warmup+50
draws beats MM2's full-budget error spam (402k errors). Restricted to the 7
firing gpcm chains the restart itself costs a summed 1.06x vs MM2 on those
chains (per-chain 0.73–2.23; the discarded attempt is cheap when the pin
spam was expensive and vice versa). Honest total-gradient view for gpcm GMD
(incl. discarded attempts): ESS/grad_total vs A0 = 0.54 (grads/draw 411.5 vs
A0 181.2); the sampling-stanza view is 0.903.

## Pre-registered gates — VERDICT: **GO**

- **(ii-ext) gpcm recovery: PASS.** Guard fires on exactly the pinned chains
  (7/7, no misses, no extras); GMD/A0 ESS = 1.226 >= 0.9 at population level
  (per-rep 1.172 / 1.111 / 1.226, min 0.87 in the boundary-flip record);
  firing outputs md5-exact MM1. ESS 2.1 -> 658.6 vs A0 537.4; rhat>1.02
  columns 550 -> 0; errors 402k -> 241k.
- **(iii) benefit models: 5/5 PASS.** Guard silent everywhere (0 fires);
  GMD == MM2 byte-identical (md5 12/12 each; ESS ratio exactly 1.000);
  GMD/A0 ESS/grad: hier_gp 3.939, hier_2pl 1.628, dogs 1.619, election88
  1.537, gp_regr 1.532 — all >= 1.05 (the wins survive the guard).
- **Residuals (reported, expected):** lsat 0.561 / 8sch_c 0.561 / blr 0.835
  GMD/A0 ESS/grad — guard silent (md5 = MM2), the mild harm stays. The guard
  converts only the PIN failure mode, not economic harm; honest residual.
- **Overall wall:** GMD never exceeds MM2 by more than 1.4% on any model and
  is 12.6% cheaper on gpcm.

GO: guarded-MM2 is the safe per-model lever — benefit-class wins locked in
byte-identically, gpcm-class catastrophe converted to MM1-parity-or-better
at <=1.06x restart cost on the affected chains only. PR candidate
(feature flag, default off: `--min-micro-guard`).

## Caveats (honest)

- election88 remains a marginal baseline (A0 rhat>1.02 on 102 cols, beta.1
  mode split; MM2/GMD per-rep ESS/grad 0.28/1.72/1.44 — rep0 below 1).
  Median passes the gate; the model is init-fragile, not guard-fragile.
- hier_gp baselines stay degenerate-consistent (rhat>1.02 on 222 cols in
  MM2/GMD vs 1143 in A0; W-80b's caveat unchanged).
- Guard detection is a pin signature (unique/probe < 0.5), not a general
  chain-health oracle; near-threshold slow chains (nu50 ~30-40 on 8sch_c/blr)
  stay silent by design and were verified silent.

## Composition requirement (recorded for the PR)

Guarded MM2 REQUIRES the step-adapter NaN guard (ef524a5 = 6ba0798) in the
same binary. Without it, the gpcm-class failure path is abort-not-pin: a
failed logp eval gives NaN min-accept, poisons the adapter, and dies at the
warmup->sampling freeze (`validate_positive(macro_time)` terminate) — the
process never reaches the sampling-phase probe, so `--min-micro-guard` would
never see anything to guard. The 241k residual errors in the GMD arm are the
discarded attempts' spam, and they only exist as *completable* runs because
the adapter guard keeps the chain alive through them.

## Paths

- Runs: `scratch/w82/runs/<A0|MM2|GMD>/<model>/rep<r>_c<chain>.{csv,log}`
- Driver / analyzer / JSON: `scratch/w82/{driver.py,analyze_w82.py,WORKERS}`,
  `scratch/w82/w82_results.json`, `scratch/w82/analyze.out`, `scratch/w82/driver.log`
- Binary: `external/walnutpie_mm2guard/build_mg/examples/stan_cli`
  (branch `robustness/mm2-guard`, HEAD ef524a5)
