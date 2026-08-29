# W-81: Combined-stack benchmark — exp-tip sampler × SoA .so on the W-36 grid

Pre-registration: WORKLOG "W-81 PRE-REGISTRATION ... COMBINED-STACK
benchmark" (2026-08-26). Arms: the W-36 grid protocol verbatim (w1000
s1000, 4 sequential single-chain invocations per rep, 3 reps, seeds
20260819+1000*rep+c, W-36 init assignment, everything else DEFAULT — no
`--metric-window`). stock_seq and exp_seq REUSED from W-36
(results/session_benchmark_w36.md); the NEW arm **exp_soa** = the
READ-ONLY exp binary (`external/walnutpie/build_w36exp/examples/stan_cli`,
@43b6435, never rebuilt) × SoA-patched .so.

## Builds (step 1)

- SoA .so source tree: `scratch/w53/bs_w53` (batch012+fused). Verified
  before building: the tree reverse-applies
  `scratch/w57/w59_soa_batch012_fused_bundle.patch` cleanly and no math
  header has changed since the W-59-era model .so builds (last edit Aug 24
  23:08 < .so mtimes 23:11) — the 4 existing parity .so are fused-tree
  builds. Pre-flight canary re-run: hier_2pl patched .so reproduces the
  recorded draws md5 `fe7c57c99a7a6530ce2dcc408d6e9c65` (W-29 protocol)
  with the current on-disk binary state.
- 7 fresh builds (radon_partially_pooled_noncentered, bym2_offset_only,
  diamonds, lsat_model, pilots, eight_schools_centered, lotka_volterra):
  per-variant dirs `scratch/w81/model_<m>/` (copy of `models/<m>.stan`,
  W-27 cache gotcha avoided), `BRIDGESTAN=scratch/w53/bs_w53`,
  `bridgestan.compile_model(make_args=["-j2"])`, one at a time,
  `env -u LD_LIBRARY_PATH`, /usr/bin/make (merged-usr identical). Build
  times 11–26 s each. `bs_w53/src/bridgestan.o` left untouched (current).
- 3 reused as-is: hier_2pl, kronecker_gp, accel_gp
  (`scratch/w53/model_<m>_patched/*.so`, copied into `scratch/w81/model_<m>/`).
  gp_regr (the 4th parity model) is not on the W-36 grid.
- Verification: all 10 load via BridgeStan; model name and
  param_unc_num() equal the W-36 `.so` (`bs_models_threads/model_<m>.so`)
  for every model (radon 389, bym2 3845, hier_2pl 669, diamonds 26,
  lsat 1006, accel 66, kronecker 438, pilots 18, eight_schools 10,
  lotka 8) — `scratch/w81/so_verify.json`.

## HEADLINE: end-to-end cross-.so bit-identity on the full grid (step 3)

**Every completed chain of the exp_soa arm is md5-IDENTICAL to W-36's
exp_seq chain CSVs: 112/112 chains (28/28 live cells).** Same exp binary,
stock-math STAN_THREADS .so (W-36) vs SoA-patched non-threads .so (W-81)
→ byte-identical draws. Combined with W-36's own stock_seq==exp_seq
canary this composes a three-way identity: stock binary × stock math ==
exp binary × stock math == exp binary × SoA math.

- **logp_grad calls exactly equal per chain, 112/112** (e.g. hier_2pl
  rep0: 36622/36325/37136/36711 in both arms) — identity at the
  trajectory level, not just the output level.
- **The two documented deterministic dead cells reproduce bit-exactly**:
  kronecker_gp rep0 and lotka_volterra rep1 abort at chain 0 with the
  identical `std::invalid_argument: macro_time must be in (0, inf)` after
  the identical call sequence (31002 calls at last stanza); the path-
  normalized logs (source paths + timing lines removed) are md5-equal
  (`c6899ca2…`, `29d2a3bd…`), 62012 lines each.
- **ESS/R-hat therefore identical by construction** — the W-36 quality
  table applies verbatim to exp_soa (spot-check table below). No numeric
  recomputation needed; the draws are the same bytes.

## Wall table (primary, per pre-registered protocol)

Walls = batch elapsed per rep (4 sequential chains), medians of 3 reps
(dead rep excluded for kronecker_gp/lotka_volterra, as in W-36):

| model                              | stock_seq | exp_seq | exp_soa | soa/stock | .so-ratio (soa/exp_seq) |
|------------------------------------|----------:|--------:|--------:|----------:|------------------------:|
| radon_partially_pooled_noncentered | 66.91     | 64.44   | 65.75   | 0.983     | 1.020                   |
| bym2_offset_only                   | 116.23    | 113.47  | 121.37  | 1.044     | 1.070                   |
| hier_2pl                           | 161.18    | 155.06  | 175.56  | 1.089     | 1.132                   |
| diamonds                           | 11.10     | 9.68    | 11.33   | 1.021     | 1.171                   |
| lsat_model                         | 38.23     | 36.57   | 41.17   | 1.077     | 1.126                   |
| accel_gp                           | 5.50      | 5.30    | 5.93    | 1.078     | 1.118                   |
| kronecker_gp                       | 70.36     | 65.14   | 73.42   | 1.044     | 1.127                   |
| pilots                             | 1.03      | 0.98    | 1.16    | 1.126     | 1.184                   |
| eight_schools_centered             | 0.58      | 0.58    | 0.69    | 1.187     | 1.187                   |
| lotka_volterra                     | 9.84      | 8.89    | 10.10   | 1.026     | 1.136                   |
| **GEOMEAN (10 models)**            |           |         |         | **1.066** | **1.126**               |

**These cross-session wall ratios are CONTAMINATED and must not be read
as a sampler/.so regression.** W-36 measured exp_seq on an otherwise
idle machine; the exp_soa grid ran under sustained foreign load from
three parallel sessions (sibling pathfinder/kronecker/compile streams at
~99% each). Load ledger (1-min loadavg at rep start): 3.1–4.8 during
rep0, 3.1–3.5 rep1, 2.1–3.1 rep2 (per-rep values in
`scratch/w81/runs/<model>/rep<r>_wall.json`). Per-chain µs/call medians
vs W-36 idle are inflated +2% (radon) to +26% (diamonds), with the
inflation largest where per-call work is smallest — a foreign-load
signature, not a code effect (a real .so regression would hit the
record-heavy models hardest, and radon — the least-contaminated window —
sits at +2%). The pre-registered −3..−7% band is unresolvable at this
noise level; the honest resolution is the interleaved control below.

## Interleaved control: the load-robust .so ratio (contamination decomposition)

NOT a new experimental arm — a control, same grid protocol (4 sequential
chains per arm, w1000/s1000, W-36 seeds/inits), alternating
stock/soa at CHAIN granularity so foreign-load drift cancels to first
order; per-chain CPU time (rusage) is the load-immune metric. Stock arm
= pristine bridgestan-2.9.0 bundle .so (`scratch/w81/model_<m>_stock/`,
7 fresh builds + 3 reused W-53 stock) — the identical build configuration
the SoA .so differs from by the math patch alone (the W-53..59 comparison
design). Binary: the same READ-ONLY build_w36exp CLI.

hier_2pl (control2, stable load 2.1–2.9): paired CPU-time ratios
0.948/0.931/0.939/0.898 → **mean 0.929** (wall 0.930, µs/call 0.930) —
**−7.1% wall-level SoA win, at the favorable edge of W-59's −5..−7%
in-sampler band, now measured under the full grid protocol.**

Per-model CPU-time ratios (control3, chain-interleaved, live init cells —
rep0, kronecker rep1 / lotka rep0):

| model                              | cpu-ratio (soa/stock) | wall-ratio | pairs (c0..c3)        |
|------------------------------------|----------------------:|-----------:|-----------------------|
| hier_2pl                           | 0.929                 | 0.930      | .948/.931/.939/.898   |
| radon_partially_pooled_noncentered | 0.984                 | 0.984      | .991/1.003/.976/.968  |
| bym2_offset_only                   | 0.919                 | 0.920      | .915/.922/.921/.919   |
| diamonds                           | 1.017                 | 1.017      | 1.072/1.017/1.012/.968|
| lsat_model                         | 0.913                 | 0.913      | .910/.915/.910/.917   |
| accel_gp                           | 0.920                 | 0.919      | .909/.916/.939/.915   |
| kronecker_gp                       | 0.975                 | 0.974      | .978/.966/.986/.968   |
| pilots                             | 1.008                 | 1.006      | 1.008/1.003/1.010/1.010|
| eight_schools_centered             | 1.007                 | 0.995      | 1.014/.995/1.019/1.000|
| lotka_volterra                     | 0.986                 | 0.985      | .995/.998/.957/.992   |
| **GEOMEAN (10 models)**            | **0.965**             |            |                       |

Clean regime split, mechanistically consistent with which log-density
paths exercise the patched generic eltwise ops: record-heavy eltwise
models win big (lsat −8.7%, bym2 −8.1%, accel_gp −8.0%, hier_2pl −7.1%);
GLM-primitive models (diamonds +1.7%, radon −1.6%, pilots +0.8%,
eight_schools +0.7% — normal_id_glm_lpdf-style specialized primitives
route around the patched ops, exactly W-60's rejected-demonstrator
reasoning); kronecker (eigen/decomposition-dominated) −2.5%, lotka
(ODE-dominated) −1.4%. All per-model ratios land in 0.91..1.02 — inside
the task's plausible band (0.90..1.00) except diamonds at 1.017 with
noisy pairs (.968..1.072, a 10-chain-seconds model).

## Multiplicativity check (the pre-registered deliverable)

- Deterministic mechanism: unchanged from W-59 — callgrind Ir −17.82%T /
  −19.06%G bit-exact; here confirmed at grid scale by the exact call-
  count equality and byte-identity above.
- Wall-level .so effect on the exp binary (interleaved CPU-time control,
  per model): hier_2pl −7.1% — at the favorable edge of and consistent
  with W-59's −5..−7% in-sampler band, now under the full grid protocol.
  Full regime split above; **grid geomean 0.965 — inside the
  pre-registered −3..−7% expectation band**, with per-model values
  0.91..1.02 (all in the task's 0.90..1.00 band except the noisy tiny
  GLM diamonds at 1.017).
- Combined-stack wall expectation exp_soa/stock_seq ≈ exp_seq/stock ×
  (0.93..0.97) ≈ 0.88..0.92: NOT verifiable from the contaminated grid
  walls (measured geomean 1.066 under load). What IS established end to
  end: the draws do not change at any level of the stack (0 draws
  changed across the binary change AND the math-library change, on all
  28 live cells + both dead cells), and the .so wall win multiplies
  regime-dependently (−7..−9% on eltwise-heavy models, ~0 on
  GLM-primitive models). The clean-machine wall confirmation of the
  combined number needs a quiet re-run of the 30-cell grid (≤25 min) —
  deferred, not refuted.

## ESS spot-check (identical by construction)

arviz rank-normalized (W-36 values; exp_soa draws are the same bytes):

| model                     | bulk ESS-min | tail ESS-min | R-Hat max |
|---------------------------|-------------:|-------------:|----------:|
| radon_partially_pooled_nc | 74.0 | 206.7 | 1.0624 |
| bym2_offset_only †        | 4.2 | 4.0 | 4.9345 |
| hier_2pl                  | 624.7 | 800.2 | 1.0093 |
| diamonds †                | 4.4 | 11.1 | 3.6341 |
| lsat_model                | 730.1 | 1255.0 | 1.0112 |
| accel_gp †                | 4.3 | 4.0 | 4.1769 |
| kronecker_gp              | 48.1 | 67.0 | 1.0894 |
| pilots †                  | 4.6 | 11.5 | 3.0478 |
| eight_schools_centered    | 101.3 | 153.9 | 1.0380 |
| lotka_volterra            | 174.2 | 268.4 | 1.0199 |

(† init-quality artifacts of the shared W-36 init protocol, present
identically in every arm since W-36.)

## Honest limitations

1. Wall table vs W-36 is cross-session under foreign load — flagged,
   not corrected post-hoc; the load ledger ships with the raw artifacts.
2. The grid used SoA non-threads .so vs W-36's STAN_THREADS stock .so
   (bs_w53 cannot build STAN_THREADS .so — documented gotcha); the
   pre-registration accepts this for sequential arms, and the interleaved
   control removes the confound by comparing same-config builds.
3. The interleaved control ran during residual load ~2.1–2.9; CPU-time
   ratios are robust to it, wall ratios marginally less so.
4. W-36's own rep2 walls show their machine was not perfectly quiet
   either (their radon rep2 75.5 vs 64.4/63.5) — medians on both sides.

## Quiet-machine confirmation (deferred item, closed 2026-08-26 evening)

Re-run of the full 30-cell wall grid on a quiet machine (1-min loadavg
0.18-0.27 at start; max 1.81 during the grid = the sampler's own load;
no foreign streams). Protocol verbatim: w1000 s1000, 4 SEQUENTIAL
single-chain invocations per cell, 3 reps, seeds 20260819+1000*rep+c,
W-36 init assignment, ALL DEFAULTS except --seed/--init-file/--output,
READ-ONLY exp binary `build_w36exp/examples/stan_cli`, OMP_NUM_THREADS=1,
LD_LIBRARY_PATH unset. CELLS STRICTLY SEQUENTIAL (1 at a time, wall =
cell batch elapsed; ~45 min total). ORDER USED (stated): rep-major with
arm alternation — for each rep: stock batch (10 models, fixed CORE grid
order) then soa batch (same order). Arms: **stock** = 10 FRESH
pristine-bundle .so (`scratch/w81/quiet_stock/<m>/`, BRIDGESTAN=
bridgestan-2.9.0, per-variant dirs, -j2 serial, 11-25 s each; all 10
load with name + param_unc == CORE_SET values, `quiet_stock_verify.json`);
**soa** = the existing SoA .so (`scratch/w81/model_<m>/`). All 4
expected dead cells reproduced deterministically (kronecker_gp rep0,
lotka_volterra rep1, chain 0, both arms).

| model                              | stock | soa  | soa/stock | CPU-ctl | soa/W36stock | drift |
|------------------------------------|------:|-----:|----------:|--------:|-------------:|------:|
| radon_partially_pooled_noncentered | 57.12 | 56.68 | 0.992 | 0.984 | 0.847 | 0.886 |
| bym2_offset_only                   | 123.71 | 112.51 | 0.909 | 0.919 | 0.968 | 1.090 |
| hier_2pl                           | 159.04 | 149.67 | 0.941 | 0.929 | 0.929 | 1.026 |
| diamonds                           | 10.73 | 10.72 | 0.999 | 1.017 | 0.966 | 1.109 |
| lsat_model                         | 39.43 | 36.28 | 0.920 | 0.913 | 0.949 | 1.078 |
| accel_gp                           | 5.62 | 5.13 | 0.914 | 0.920 | 0.934 | 1.059 |
| kronecker_gp                       | 68.50 | 66.36 | 0.969 | 0.975 | 0.943 | 1.052 |
| pilots                             | 1.03 | 1.04 | 1.009 | 1.008 | 1.007 | 1.049 |
| eight_schools_centered             | 0.60 | 0.61 | 1.027 | 1.007 | 1.052 | 1.024 |
| lotka_volterra                     | 9.51 | 9.18 | 0.965 | 0.986 | 0.932 | 1.070 |
| **GEOMEAN**                        |       |      | **0.964** | **0.965** | **0.951** | **1.043** |

**VERDICT — the clean-machine confirmation CONFIRMS the .so effect.**
The load-free within-session wall ratio soa/stock = **0.964 geomean**,
statistically indistinguishable from the interleaved CPU-time control's
0.965, with per-model agreement to ±0.02 on every model except the
0.6-s eight_schools (1.027 vs 1.007 — timer noise). The regime split
survives at wall level: eltwise/record-heavy models win (bym2 −9.1%,
accel_gp −8.6%, lsat −8.0%, hier_2pl −5.9%), GLM-primitive models are
flat (diamonds −0.1%, radon −0.8%, pilots +0.9%), kronecker −3.1%,
lotka −3.5%. The pre-registered −3..−7% band holds; the contaminated
table's 1.066 / .so-column 1.126 were pure load inflation (~+12% on the
soa arm: 1.066/0.951).

- **Cross-session combined number vs the 0.88..0.92 expectation**: my
  soa / W-36 stock_seq reads **0.951** — ABOVE the band, but the excess
  is fully accounted for by machine drift: 0.951 = 0.964 (.so, clean) x
  1.043 (today's machine vs W-36 session, measured directly by the stock
  arm vs W-36 exp_seq) x 0.947 (W-36's own threading win). Drift-
  corrected combined = 0.964 x 0.947 = **0.913 — inside 0.88..0.92**.
- **Drift check (stock arm vs W-36 exp_seq, same binary)**: geomean
  1.043 — today's quiet machine is ~4% slower than the W-36 session was,
  scattered per model (radon 0.886 FASTER today .. diamonds 1.109;
  vs W-36 stock_seq the same arm reads 0.987). Cross-session per-model
  wall comparison has a ±5-10% machine floor; only the within-session
  paired ratio (0.964) is drift-free. Per-rep walls are tight within
  models (hier_2pl stock 158.8/159.0/162.2, soa 149.7/148.8/151.4).
- **Draws identity on the quiet grid**: my soa-arm chain CSVs are
  md5-EQUAL to the earlier exp_soa csvs on the 4 spot-check models
  (hier_2pl, lsat_model, bym2_offset_only, kronecker_gp — 44/44 chains);
  bonus: my pristine-stock-arm CSVs are md5-EQUAL to W-36's exp_seq csvs
  (44/44 chains, 4 models incl. lotka rep0/2) — pristine non-threads .so
  reproduces the W-36 STAN_THREADS .so bit-exactly, extending the W-36/
  W-81 identity chain to four corners: {stock,exp} binary x {threads,
  non-threads stock, SoA} math, zero draws changed anywhere.

## Raw artifacts

- Builds: `scratch/w81/build_missing.py`, `build_stock.py`,
  `verify_so.py` (+ `so_verify.json`), model dirs `scratch/w81/model_<m>/`
  (SoA) and `scratch/w81/model_<m>_stock/` (pristine).
- Grid: `scratch/w81/run_soa.py`, outputs `scratch/w81/runs/<model>/
  rep<r>_c<c>.{csv,log}` + `rep<r>_wall.json` (wall, loads, stanza sums,
  per-chain md5/calls). Analysis: `scratch/w81/analyze_soa.py` +
  `w81_analysis.json`.
- Controls: `scratch/w81/control_interleaved.py` (batch-granular, load-
  noise-dominated — kept as the negative example), `control_cpu.py` +
  `control2/` (hier_2pl chain-granular), `control_all.py` + `control3/`.
- Reused W-36 artifacts: `runs/w36/exp_seq/`, `results/w36_wall.json`,
  `results/w36_ess.json`.
- Quiet confirmation: `scratch/w81/quiet_build` (in-line loop),
  `quiet_stock/<m>/` + `quiet_stock_verify.json`, runner `quiet_run.py`
  + `quiet_run.log`, outputs `quiet_runs/<arm>/<model>/rep<r>_c<c>.{csv,log}`
  + `rep<r>_wall.json` (wall + loads + per-chain md5/calls), analysis
  `quiet_analyze.py` + `quiet_analysis.json`.
