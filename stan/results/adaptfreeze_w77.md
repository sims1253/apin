# W-77: adapt-freeze (--adapt-freeze-iters 400) — CLOSE-OUT: NO-GO, hypothesis refuted in the OPPOSITE direction (freezing adaptation at 400 makes sampling-phase grads 2.22x MORE expensive at 0.53x ESS — the late half of warmup adaptation is productive, not an over-adaptation tax)

Pre-registration: WORKLOG "W-77 PRE-REGISTRATION (adapt-freeze)" +
its AMENDMENT (same-binary arms design). Binary:
`external/walnutpie_adaptfreeze/build_af/examples/stan_cli`
(branch `exp/adapt-freeze` @ db8cbd8). Exact CLI flag spelling
(from `--help`): **`--adapt-freeze-iters UINT:NONNEGATIVE [0]`** —
"Freeze all adaptation at warmup iteration N: the step adapter, mass
estimator (incl. low-rank factors and window resets), and min-micro-steps
estimator stop updating and stay frozen at their N-iteration state, while
warmup transitions CONTINUE for the full budget under the frozen tuning
(positions keep exploring; warmup reporting keeps firing). Isolates
adaptation duration from position quality (0 = off; N >= warmup iterations
never freezes)".

## Design (as pre-registered + amended)

- ONE binary, BOTH arms on it (no codegen confound): **N0** = no freeze
  flag (fresh same-binary baseline); **F400** = `--adapt-freeze-iters 400`.
- All 21 CORE_SET models (`scratch/w63/manifest.csv`), args identical to
  the W-63 grid: w1000 s1000, pf inits (manifest init_dirs),
  `--metric-window 50`, single chain per process, seeds
  20260819+1000*rep+chain, `env -u LD_LIBRARY_PATH`, `OMP_NUM_THREADS=1`.
- 2 x 21 x 3 x 4 = **504 runs**; driver `scratch/w77/driver.py` (adapted
  from `scratch/w63/driver.py`; WORKERS=4, resume-capable, arm-innermost
  dispatch so both arms of a cell run adjacently — the W-74 temporal
  load-pairing lesson).
- Completion: **504/504, 0 failures, 37 min wall** (00:16:25–00:53:35),
  machine otherwise idle; per-call times balanced across arms (median
  0.30 vs 0.26 us/call, p90 1.42 vs 1.39) — wall ratios this session are
  fair, and grads ratios are load-invariant regardless.
- Baselines reused: W-63 A0 w1000 grid `scratch/w63/runs/A0/<model>/w1000_pf/`
  (G1a + tie-back) and W-74 W400 `scratch/w74/runs/W400/<model>/` (tie-back).

## Conventions (reused from w63/w74/w76)

ESS_min = min over parameters of rank-normalized Geyer ess_bulk on the
combined 4 chains per rep; rep medians reported; rank-normalized
split-R-hat; constant-column exclusion. Each chain log has 2 stanzas
(warmup, sampling); **sampling-phase grads** = last `logp_grad calls:`
stanza; warmup-phase = the first. grads/draw = calls / 1000 draws.
Wall = sum of both `total time:` stanzas over the 4 chains. Headline
ESS/s = ess_min_med / wall_med.

## Gates

- **G1a PASS, strongest form**: N0 vs W-63 A0 — all **252/252 CSVs
  md5-IDENTICAL** (0 mismatches, 0 no-baseline). The feared W-54 codegen
  perturbation did not materialize; N0 is a bit-exact reproduction of the
  W-63 A0 grid, which makes the same-binary N0 baseline airtight (the
  statistical rep-noise band was never needed; all ESS ratios exactly 1).
- **G1b PASS** (recorded from the build session): ctest 225/225 PASS
  (`build_af_tests`, tests-only configure so the campaign binary was
  untouched); standalone property suites PASS with W-62/W-66-matching
  values — low_rank_metric_test (cond(lowrank-precond)=19.3126,
  rel-dense 4.26e-17, roundtrip 1.08e-16), leapfrog_property_test
  (reversibility 3.3e-17, |detJ|-1 8.9e-16).
- **G2 FAIL**: F400/N0 ESS_min ratio >= 0.9 on ALL models — **15/21
  violators**, min **0.078 (radon_pp)**; also hier_2pl 0.217,
  eight_schools_centered 0.222, kidscore 0.253, 8sch_nc 0.255,
  lsat 0.284, lotka 0.298. Only 6 pass: wells 1.377, arma11 2.077,
  ldgm 1.038, dogs 0.962, accel 0.931, pilots 0.906.
- **G3 FAIL, both prongs, reversed**: geomean sampling-phase grads/draw
  ratio **2.223** (gate <= 0.92; hypothesis said ~0.76) AND geomean
  ESS/s **0.288** (gate >= 1.05). Warmup-phase grads also rise (geomean
  1.698); total-call ratio geomean 1.932; ESS geomean 0.527.
- **G4 FAIL**: new pathologies vs N0 census — pins: blr 0->1,
  diamonds 0->3, radon_pp 0->2, pilots 0->9, accel_gp 2->6,
  bym2 5->12; rhat>1.02 med counts worse on 12 models (worst:
  radon_pp 1->162, kronecker 1992->3793, pilots 16->58,
  hier_2pl 0->18); logp_grad errors worse on 6 (blr 28552->49877,
  accel 582->62608, kronecker 65228->76138).
- **GO: FALSE** (G2+G3+G4 all fail). Recorded as a clean negative: the
  pre-registered alternative "position effect (or the estimator needs the
  tail) — NULL or harm" is confirmed as harm.

## Per-model mechanism table (F400/N0, rep medians)

| model | ESS ratio | sampling grads ratio | ESS/s ratio | warmup grads ratio | F400 gS/draw | N0 gS/draw |
|---|---|---|---|---|---|---|
| eight_schools_noncentered | 0.255 | 1.613 | 0.213 | 1.320 | 56.6 | 35.1 |
| blr | 0.734 | 1.590 | 0.520 | 1.240 | 147.2 | 92.6 |
| kidscore_momiq | 0.253 | **6.575** | 0.066 | 3.658 | 318.3 | 48.4 |
| lsat_model | 0.284 | **10.216** | 0.042 | 5.007 | 751.3 | 73.5 |
| logmesquite_logvash | 0.387 | 2.106 | 0.236 | 1.657 | 145.4 | 69.1 |
| wells_dist100_model | **1.377** | 1.471 | **1.023** | 1.212 | 40.9 | 27.8 |
| diamonds | 0.875 | 2.533 | 0.491 | 1.354 | 253.3 | 100.0 |
| radon_partially_pooled_noncentered | **0.078** | 3.156 | 0.032 | 2.058 | 224.1 | 71.0 |
| radon_variable_intercept_slope_noncentered | 0.567 | 4.526 | 0.166 | 2.781 | 300.5 | 66.4 |
| dogs_hierarchical | 0.962 | 1.303 | 0.812 | 1.121 | 29.6 | 22.8 |
| pilots | 0.906 | **0.851** | 0.996 | 1.222 | 171.9 | 202.1 |
| hier_2pl | 0.217 | **6.006** | 0.050 | 3.096 | 404.7 | 67.4 |
| gp_regr | 0.614 | 1.665 | 0.411 | 1.345 | 43.2 | 26.0 |
| kronecker_gp | 0.539 | 3.249 | 0.198 | 2.148 | 235.3 | 72.4 |
| accel_gp | 0.931 | 3.013 | 0.325 | 2.804 | 481.5 | 159.8 |
| bym2_offset_only | 0.881 | 1.166 | 0.898 | 0.880 | 128.0 | 109.7 |
| eight_schools_centered | 0.222 | 1.060 | 0.218 | 1.264 | 88.3 | 83.4 |
| garch11 | 0.715 | 1.159 | 0.656 | 1.052 | 53.1 | 45.8 |
| lotka_volterra | 0.298 | 1.081 | 0.320 | 1.188 | 88.1 | 81.5 |
| low_dim_gauss_mix | 1.038 | 2.078 | 0.586 | 1.509 | 88.7 | 42.7 |
| arma11 | 2.077 | 2.857 | 0.900 | 2.008 | 79.2 | 27.7 |
| **geomean** | **0.527** | **2.223** | **0.288** | **1.698** | | |

Reading: sampling-phase grads/draw rises on 20/21 models (only pilots
falls, 0.851); the rise is largest exactly where adaptation matters most
(lsat 10.2x, kidscore 6.6x, hier_2pl 6.0x). Even the ESS "gainers"
(wells, arma11, ldgm) pay 1.5-2.9x sampling grads for it — ESS/grad
worsens on 20/21 (wells is the sole wash: ESS/s 1.023, still grads up).

## Mechanism verdict (the W-74 question answered)

The pre-registered hypothesis — "W-74's 1.32x ESS-per-call at W400 is an
adaptation-duration effect (over-adapted tuning drives unproductive
trajectory spend); freeze400 captures per-call efficiency at full
position quality" — is **refuted in the opposite direction**: freezing
all adaptation at iteration 400 (while warmup keeps transitioning) locks
in an UNDER-adapted step/metric, and the sampling phase then pays MORE
gradients per draw (2.22x geomean) for LESS ESS (0.53x geomean). The
late 600 warmup iterations of continued adaptation are on-net PRODUCTIVE
on both quality and per-draw cost; there is no over-adaptation tax to
harvest. This closes the mechanism isolate cleanly: W-72's estimator
discounting (changing WHAT is estimated) failed; W-74's truncation
(changing the budget) failed on ESS; W-77 shows the remaining branch —
same budget, frozen tuning — fails on cost AND quality.

## W-74 tie-back (recomputed with the same estimators)

W-74's recorded W400 efficiency was a TOTAL-call metric. Recomputed here
from the same logs: W400/W1000 TOTAL-call ratio geomean **0.682**
(W-74 recorded 0.695) and ESS per TOTAL call geomean **1.347**
(W-74 recorded 1.32) — reconciled. But W400's SAMPLING-phase calls were
~parity (**0.970** geomean, ESS/samp-call 0.964): **all of W-74's
gradient saving came from the 600-iteration warmup BUDGET cut, none from
a better sampling state.** F400 (same full budget, tuning frozen at the
same iteration 400 W-74 stopped at) shows what that tuning state is
actually worth: total calls 1.932x, sampling calls 2.223x, ESS 0.527x.
So the two campaigns triangulate: W-74's 1.32x per-call = budget
arithmetic; the 400-iteration adaptation state itself is far from
converged on CORE_SET, and "does freezing at 400 reproduce W-74's 1.32x
at full position quality" answers **no — it produces the inverse**
(per-call cost 2.22x at collapsed position quality).

## Files

- Runs: `scratch/w77/runs/{N0,F400}/<model>/rep<r>_c<chain>.{csv,log}`
- Driver / logs: `scratch/w77/driver.py`, `driver.log`, `WORKERS`
- Analyzer + output: `scratch/w77/analyze_w77.py`, `analyze.out`,
  `w77_results.json`
- Property suites (built this session, clang++-22 -O2):
  `scratch/w77/low_rank_metric_test`, `leapfrog_property_test`
- Tests build (tests-only configure, campaign binary untouched):
  `external/walnutpie_adaptfreeze/build_af_tests/` (ctest 225/225)
- Branch `exp/adapt-freeze` @ db8cbd8 (default-off flag; not a
  default-change candidate — negative verdict recorded).
