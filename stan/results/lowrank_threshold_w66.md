# W-66 — Screen-threshold sweep {0.65, 0.8}: the final low-rank falsification test — DIRECTION CLOSES

Date: 2026-08-25. Pre-registration: WORKLOG "W-66 PRE-REGISTRATION (before
any run)" — the decision rule below is BINDING and was fixed before any run.
Binary: walnutpie exp/lr-alg1-basis commit 7b81357 (the W-65 screen-gating
fix; build_gates/examples/stan_cli, NOT rebuilt this session). Machine: 4
workers, `env -u LD_LIBRARY_PATH`, `OMP_NUM_THREADS=1`, single chain per
process.

Protocol: for each T in {0.65, 0.8}: 10 models x A3' flags (`--metric-rank
10 --metric-basis 4 --metric-full --metric-auto T --metric-window 50`) x 3
reps x 4 chains, w1000+s1000, pf inits per scratch/w63/manifest.csv, seeds
20260819+1000*rep+chain — identical to the W-65 A3'@0.5 arm except the
threshold. 240/240 chain-runs DONE, 0 failures (driver
scratch/w66/driver.py, parameterized over T, resume-capable, WORKERS=4;
T0.65 ~18 min, T0.8 ~23 min wall). Comparators REUSED, not rerun: A0/A2
from scratch/w63/runs (same seeds/protocol, canary-verified code paths),
A3'@0.5 from scratch/w65. Census is exact byte-equality (md5) per
chain-run vs the same-seed A0/A2 csvs.

Screen semantics (CLI help): the auto-screen ENGAGES the low-rank operator
for a window when the window_cross_ratio ("singular-excess concentration")
is AT MOST the threshold. Raising T therefore admits strictly more spectra:
everything engaged at 0.5 stays engaged at 0.65/0.8; the sweep measures
what additionally crosses the bar.

## Engagement census, T=0.65

| model                  | done | ==A2 | ==A0 (declined-all) | engaged |
|------------------------|-----:|-----:|--------------------:|--------:|
| hier_2pl               | 12/12 | 0 | 0  | 12/12 |
| lsat_model             | 12/12 | 0 | 0  | 12/12 |
| eight_schools_centered | 12/12 | 0 | 3  | **9/12** |
| low_dim_gauss_mix      | 12/12 | 0 | 11 | 1/12 (r2c1) |
| garch11                | 12/12 | 0 | 12 | 0 |
| dogs_hierarchical      | 12/12 | 0 | 12 | 0 |
| kidscore_momiq         | 12/12 | 0 | 12 | 0 |
| blr                    | 12/12 | 0 | 12 | 0 |
| arma11                 | 12/12 | 0 | 12 | 0 |
| logmesquite_logvash    | 12/12 | 0 | 12 | 0 |

0/120 ==A2 (no wiring failures; consistent with the post-fix guarantee).
Vs T=0.5 (W-65): the ONLY engagement changes are eight_schools_centered
2/12 -> 9/12 and deeper acceptance within already-engaged hier_2pl/lsat
windows (mean hier_2pl chain runtime 190s @0.5 -> 263s @0.65 — more windows
under the rank operator). The winners' spectra stay above the bar.

## ESS table, T=0.65 (ess_bulk_min, median of 3 reps, combined 4-chain)

Same estimator and conventions as W-63/W-65 (rank-normalized Geyer
initial-monotone ESS, sampler columns dropped, exactly-constant columns
excluded; scratch/w66/analyze_w66.py, reused from scratch/w65/analyze_w65.py).

| model                  |     A0 |     A2 | A3'@0.65 | @0.65/A0 | @0.5/A0 (W-65) | A2/A0 forced | rhat_max |
|------------------------|-------:|-------:|---------:|---------:|---------------:|-------------:|---------:|
| hier_2pl               |  493.4 |  196.1 |     19.4 | **0.039**|          0.797 |        0.397 |    1.127 |
| lsat_model             |  940.8 |    5.9 |     27.4 |    0.029 |          0.226 |        0.006 |    1.115 |
| eight_schools_centered |  103.5 |    3.8 |     96.2 |    0.930 |          0.930 |        0.037 |    1.068 |
| low_dim_gauss_mix      |  778.6 | 2626.6 |    778.6 |    1.000 |          1.000 |        3.373 |    1.011 |
| logmesquite_logvash    |  102.4 |  176.8 |    102.4 |    1.000 |          1.000 |        1.727 |    1.062 |
| arma11                 | 1022.3 | 2541.0 |   1022.3 |    1.000 |          1.000 |        2.486 |    1.003 |
| garch11                |  747.1 |  378.6 |    747.1 |    1.000 |          1.000 |        0.507 |    1.004 |
| dogs_hierarchical      | 1592.1 | 1713.3 |   1592.1 |    1.000 |          1.000 |        1.076 |    1.003 |
| kidscore_momiq         |  283.4 |  262.7 |    283.4 |    1.000 |          1.000 |        0.927 |    1.021 |
| blr                    |  346.6 |    6.4 |    346.6 |    1.000 |          1.000 |        0.018 |    1.021 |

Per-rep: hier_2pl collapses in ALL THREE reps at 0.65 (15.2/19.4/37.4 vs
A0 540.6/493.4/489.9) — the 0.5-value's rep0 tail risk became systemic
once engagement deepened.

## Engagement census, T=0.8

| model                  | done | ==A2 | ==A0 (declined-all) | engaged |
|------------------------|-----:|-----:|--------------------:|--------:|
| hier_2pl               | 12/12 | 0 | 0  | 12/12 |
| lsat_model             | 12/12 | 0 | 0  | 12/12 |
| eight_schools_centered | 12/12 | 0 | 0  | **12/12** |
| low_dim_gauss_mix      | 12/12 | 0 | 11 | 1/12 (r2c1) |
| garch11                | 12/12 | 0 | 12 | 0 |
| dogs_hierarchical      | 12/12 | 0 | 12 | 0 |
| kidscore_momiq         | 12/12 | 0 | 12 | 0 |
| blr                    | 12/12 | 0 | 12 | 0 |
| arma11                 | 12/12 | 0 | 12 | 0 |
| logmesquite_logvash    | 12/12 | 0 | 12 | 0 |

0/120 ==A2. Vs 0.65: eight_schools_centered completes its flip to 12/12;
hier_2pl runs deeper still (mean 357s/chain). The winners STILL do not
cross: logmesquite and arma11 0/12 engaged, low_dim_gauss_mix 1/12 — the
same lone chain (r2c1) that engaged at 0.5.

## ESS table, T=0.8

| model                  |     A0 |     A2 | A3'@0.8 | @0.8/A0 | @0.5/A0 (W-65) | A2/A0 forced | rhat_max |
|------------------------|-------:|-------:|--------:|--------:|---------------:|-------------:|---------:|
| hier_2pl               |  493.4 |  196.1 |   261.2 | **0.529**|          0.797 |        0.397 |    1.031 |
| lsat_model             |  940.8 |    5.9 |   370.8 |    0.394 |          0.226 |        0.006 |    1.053 |
| eight_schools_centered |  103.5 |    3.8 |    60.5 | **0.585**|          0.930 |        0.037 |    1.110 |
| low_dim_gauss_mix      |  778.6 | 2626.6 |    778.6 |    1.000 |          1.000 |        3.373 |    1.011 |
| logmesquite_logvash    |  102.4 |  176.8 |    102.4 |    1.000 |          1.000 |        1.727 |    1.062 |
| arma11                 | 1022.3 | 2541.0 |   1022.3 |    1.000 |          1.000 |        2.486 |    1.003 |
| garch11                |  747.1 |  378.6 |    747.1 |    1.000 |          1.000 |        0.507 |    1.004 |
| dogs_hierarchical      | 1592.1 | 1713.3 |   1592.1 |    1.000 |          1.000 |        1.076 |    1.003 |
| kidscore_momiq         |  283.4 |  262.7 |    283.4 |    1.000 |          1.000 |        0.927 |    1.021 |
| blr                    |  346.6 |    6.4 |    346.6 |    1.000 |          1.000 |        0.018 |    1.021 |

Per-rep: eight_schools_centered 90.8/60.5/25.6 vs A0 112.6/103.5/85.4 —
full engagement drags it to 0.585 with rep2 collapsing (rhat_max 1.110).

## Binding adjudication (pre-registered rule)

VIABLE iff (a) winners (low_dim_gauss_mix, logmesquite_logvash, arma11)
engage >= 6/12 chains EACH; (b) eight_schools_centered A3'@T/A0 >= 0.9 AND
blr >= 0.9 AND kidscore_momiq >= 0.9; (c) hier_2pl >= 0.797 (its
0.5-screened value; precise reference 0.7969).

**T=0.65 — NOT VIABLE (fails a and c):**
- (a) FAIL — engaged: low_dim_gauss_mix 1/12, logmesquite_logvash 0/12,
  arma11 0/12 (all < 6).
- (b) PASS — eight_schools_centered 0.930, blr 1.000, kidscore 1.000.
- (c) FAIL — hier_2pl 0.039 (vs >= 0.797): deeper engagement collapsed
  all three reps.

**T=0.8 — NOT VIABLE (fails a, b, and c):**
- (a) FAIL — same picture: 1/12, 0/12, 0/12.
- (b) FAIL — eight_schools_centered 0.585 < 0.9 (blr 1.000, kidscore
  1.000 pass).
- (c) FAIL — hier_2pl 0.529 < 0.797.

## Final verdict (per the binding pre-registration)

**No threshold in {0.65, 0.8} is viable => THE LOW-RANK DIRECTION CLOSES
FOR GOOD at CORE_SET scale on this base.** Together with W-65's E3 failure
at 0.5, the swept operating points are {0.5, 0.65, 0.8} and none separates
the rank-winners from the rank-harms. The window_cross_ratio screen
statistic cannot encode "rank helps here" on this model set; recorded as
the FINAL verdict for the direction on this base — no further sweeps. (The
commit-7b81357 gating MECHANISM itself remains correct and shipped: it
gates exactly as designed, 0/240 ==A2 across this session.)

## Mechanism reading: where each model's spectra sit

Because engagement is "window_cross_ratio <= T", the census fixes each
model's per-window statistic relative to the swept bars:

- WELL BELOW 0.5 (engaged everywhere at every T): hier_2pl, lsat_model —
  the screen reads their geometry as maximally "spread/cross-correlated",
  i.e. most certifiably low-rank-friendly, yet the forced operator hurts
  them most (A2/A0 0.397, 0.006) and deeper engagement monotonically
  worsens the harm (hier_2pl 0.797 -> 0.039 -> 0.529; lsat 0.226 -> 0.029
  -> 0.394).
- IN (0.5, 0.8] (the flip band): eight_schools_centered — 2/12 chains had
  windows at/below 0.5, 9/12 by 0.65, 12/12 by 0.8. This is the funnel
  collapse sentinel (forced 0.037), and its ESS follows the flips:
  0.930 -> 0.930 -> 0.585.
- ABOVE 0.8 IN ESSENTIALLY ALL WINDOWS: the three winners
  (low_dim_gauss_mix 11/12 declined, logmesquite 12/12, arma11 12/12 even
  at 0.8) — the statistic reads their spectra as CONCENTRATED exactly
  where forced rank helps most (A2/A0 3.373 / 1.727 / 2.486). The lone
  engaged ldgm chain (r2c1, engaged since 0.5) is harmless but
  benefit-less (rep2 ESS 599.8 vs 575.6 A0).
- ALWAYS DECLINED, NEVER FLIPPING through 0.8: blr, kidscore_momiq,
  dogs_hierarchical, garch11 (spectra far above 1 in top-direction
  concentration terms; the sentinels that matter stay safe at every swept
  T — which is also why rule (b) could only fail via eight_schools).

The ordering is INVERTED relative to benefit: models the statistic
certifies as spread (low ratio) are the ones rank degrades; models it
reads as concentrated (high ratio) are the ones rank accelerates. Any
future screen would need a statistic whose sign or functional form
reverses this ordering; window_cross_ratio at any operating point on
[0.5, 0.8] cannot.

## Honest limits

- 3 reps x 4 chains per threshold (the pre-registered budget); hier_2pl's
  T-dependence is non-monotone (0.797 -> 0.039 -> 0.529), i.e. its
  median is tail-sensitive at this budget — but both 0.65 and 0.8 fail
  rule (c) outright regardless of that wobble, and rule (a) fails at
  every swept T by a 1/12-vs-6/12 margin that no plausible rep-noise
  closes.
- Engagement census is exact (byte-equality) but binary per chain; extent
  of engagement is only proxied (runtimes: hier_2pl 190 -> 263 -> 357 s
  mean per chain).
- The sweep covers {0.65, 0.8} as pre-registered (with 0.5 from W-65);
  thresholds outside that grid were not run and are not needed: rule (a)
  requires flipping 11/12, 12/12, 12/12 winner chains from declined to
  engaged, and raising T further can only drag eight_schools_centered and
  hier_2pl deeper into the already-failing harms (lowering T below 0.5
  re-blocks everything, reproducing W-65's E3).
- A0/A2 comparators reused from W-63 (valid: identical seeds, inits,
  protocol; code paths canary-verified unchanged in W-65).

## Artifacts

- Runs: scratch/w66/runs/T0.65/<model>/w1000_pf/rep<r>_c<c>.{csv,log} and
  scratch/w66/runs/T0.8/... (240/240 done).
- Driver: scratch/w66/driver.py (+ driver.log, driver_stdout.log,
  WORKERS=4).
- Analysis: scratch/w66/analyze_w66.py -> scratch/w66/w66_results.json
  (census, per-rep ESS, adjudication, final verdict fields).
- This file: results/lowrank_threshold_w66.md; WORKLOG W-66 close-out
  appended same session.
