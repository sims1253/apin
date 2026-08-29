# W-65 — Screened-full low-rank metric (A3') after the screen-gating fix

Date: 2026-08-25. Pre-registration: WORKLOG "W-65 PRE-REGISTRATION (before
any code): fix the screen to gate the full operator; re-canary; TARGETED
screened-full rerun (bounded subset, NOT a full grid)". Fix: walnutpie
exp/lr-alg1-basis commit 7b81357 (`Gate the full low-rank operator on the
auto-screen (W-65)`); worktree external/walnutpie_lowrank.

Arms (all w1000+s1000, --metric-window 50, pf inits per the W-63 manifest,
seeds 20260819+1000*rep+chain, 3 reps x 4 chains):

- A0 (default diagonal): REUSED from scratch/w63/runs/A0 (W-63, same
  seeds/protocol).
- A2 (forced full low-rank: --metric-rank 10 --metric-basis 4 --metric-full):
  REUSED from scratch/w63/runs/A2.
- A3' (screened full: A2 flags + --metric-auto 0.5): FRESH, this session,
  scratch/w65/runs/A3p (driver scratch/w65/driver.py, 120/120 chain-runs
  DONE, 0 failures, ~15 min wall at 4 workers).

Phase-1 gates (all PASS, full detail in the WORKLOG close-out):
(i) default-path canary hier_2pl/kronecker_gp byte-identical new-binary vs
build_base binary AND vs the recorded md5s
fe7c57c99a7a6530ce2dcc408d6e9c65 / 6b61df9fd30646be915c87961b2ff816;
(ii) A2-no-auto spot check (blr w100 s500 pin cell) byte-identical vs the
W-63 pre-fix binary's output (md5 fbf331a37a368184a085478ca331a289) — a
real behavioral comparison, not only by-construction; (iii) ctest 225/225 +
low_rank_metric_test (cond(lowrank-precond)=19.31, rel-dense 4.3e-17) +
leapfrog_property_test (reversibility 3.3e-17, |detJ|-1 8.9e-16). Property
suites compiled with clang++-22 -O2 (the relocated g++ toolchain is broken
in this environment: missing liblto_plugin / stdlib include prefix);
numeric gates match W-62's g++-compiled values.

## Engagement census

Byte-equality of each A3' chain-run csv vs the same-seed A2 and A0 runs.
Discriminators (exact, because a declined A3' run is bit-identical to A0 —
same diagonal transitions, same RNG stream, plain freeze — and a post-fix
A3' run can never equal A2 because the drift phase alone runs a different
operator):

- `== A2`: wiring failure (screen not consulted). OBSERVED: 0/120 chains.
- `== A0`: the screen DECLINED at every window of that chain.
- differs from both: the screen ENGAGED (accepted) at >= 1 post-drift
  window.

| model                  | done | ==A2 | ==A0 (declined-all) | engaged |
|------------------------|-----:|-----:|--------------------:|--------:|
| hier_2pl               | 12/12 | 0 | 0  | 12/12  |
| lsat_model             | 12/12 | 0 | 0  | 12/12  |
| eight_schools_centered | 12/12 | 0 | 10 | 2/12 (r0c3, r1c2) |
| low_dim_gauss_mix      | 12/12 | 0 | 11 | 1/12 (r2c1) |
| garch11                | 12/12 | 0 | 12 | 0 |
| dogs_hierarchical      | 12/12 | 0 | 12 | 0 |
| kidscore_momiq         | 12/12 | 0 | 12 | 0 |
| blr                    | 12/12 | 0 | 12 | 0 |
| arma11                 | 12/12 | 0 | 12 | 0 |
| logmesquite_logvash    | 12/12 | 0 | 12 | 0 |

The W-63 artifact (A3 byte-identical to A2 on 300/300 runs because the
screen never gated the operator) is gone: the operator is now demonstrably
screen-gated.

## ESS table (ess_bulk_min, median of 3 reps, combined 4-chain draws)

Same estimator and conventions as W-63 (rank-normalized Geyer
initial-monotone ESS, sampler columns dropped, exactly-constant columns
excluded; analysis script scratch/w65/analyze_w65.py, reused from
scratch/w63/analyze_lowrank.py).

| model                  |     A0 |     A2 |    A3' | A3'/A0 | A2/A0 (W-63 forced) | rhat_max A3' |
|------------------------|-------:|-------:|-------:|-------:|--------------------:|-------------:|
| hier_2pl               |  493.4 |  196.1 |  393.2 |  0.797 |               0.397 |        1.055 |
| lsat_model             |  940.8 |    5.9 |  212.3 |  0.226 |               0.006 |        1.039 |
| garch11                |  747.1 |  378.6 |  747.1 |  1.000 |               0.507 |        1.004 |
| dogs_hierarchical      | 1592.1 | 1713.3 | 1592.1 |  1.000 |               1.076 |        1.003 |
| kidscore_momiq         |  283.4 |  262.7 |  283.4 |  1.000 |               0.927 |        1.021 |
| blr                    |  346.6 |    6.4 |  346.6 |  1.000 |               0.018 |        1.021 |
| eight_schools_centered |  103.5 |    3.8 |   96.2 |  0.930 |               0.037 |        1.048 |
| arma11                 | 1022.3 | 2541.0 | 1022.3 |  1.000 |               2.486 |        1.003 |
| logmesquite_logvash    |  102.4 |  176.8 |  102.4 |  1.000 |               1.727 |        1.062 |
| low_dim_gauss_mix      |  778.6 | 2626.6 |  778.6 |  1.000 |               3.373 |        1.011 |

Where the screen declined at every window the A3' csvs are byte-identical
to A0, hence ESS ratios of exactly 1.000 by construction. Per-rep detail
(JSON scratch/w65/w65_results.json): hier_2pl rep0 under A3' collapses
(ess_min 25.2 vs A0 540.6) — engagement carries a heavy-tail risk on that
model; the other two reps land at 438.4/393.2.

## Verdicts

E1 — wiring (primary deliverable): **PASS.** 0/120 A3' chain-runs equal
their A2 counterpart (pre-fix it was 300/300 byte-identical); 2 models
fully engaged, 2 partially, 6 fully declined. The screen demonstrably
gates the full operator, in warmup and at the freeze.

E2 — sentinels materially better than W-63's forced-rank numbers: **PASS.**
eight_schools_centered 0.930 vs 0.037 forced (25x better, and above the
0.9x no-harm bar = the pre-registered STRONG positive, despite 2/12 chains
engaging); blr 1.000 vs 0.018; kidscore_momiq 1.000 vs 0.927;
dogs_hierarchical 1.000 vs 1.076 (the 7.6% forced-rank upside on dogs is
given up). No sentinel collapses under A3'.

E3 — winners preserved: **FAIL (screen calibration killed).** All three
W-63 rank-winners are blocked: low_dim_gauss_mix 1.000 (11/12 declined) vs
3.373 forced; logmesquite_logvash 1.000 (12/12 declined) vs 1.727; arma11
1.000 (12/12 declined) vs 2.486. Per the pre-registration this outcome
"kills the screen calibration and the direction closes": at threshold 0.5
the window_cross_ratio signal reads the winners' spectra as concentrated
(declines) exactly where forced rank helped most.

Cross-structure (secondary, not a pre-registered E-verdict): the screen
engages on hier_2pl (0.797 vs 0.397 forced — halfway back to A0, with the
rep0 tail risk above) and on lsat_model (0.226 vs 0.006 forced — 38x
better than forced but still a 4.4x loss vs A0; engagement actively hurts
there).

## Honest limits

- The engagement census is exact (byte-equality), but "engaged" only means
  the screen accepted at >= 1 window; it does not measure how many windows
  accepted or for how long the operator ran. lsat/hier_2pl show 12/12
  engaged yet land far from A2, so engagement extent varies.
- 3 reps x 4 chains is the pre-registered budget; hier_2pl rep0's collapse
  (25.2) shows single-rep tails can move a median at this budget.
- A2/A0 comparators are reused from W-63 — valid because the seeds, inits,
  protocol, and (verified by canaries) the unchanged code paths are
  identical; the A3' arm is the only new binary behavior.
- Threshold 0.5 was inherited from W-63's step0 (where the broken wiring
  made all thresholds indistinguishable); no threshold sweep has been run
  post-fix. The E3 failure is a statement about the calibrated operating
  point of window_cross_ratio, not about the gating mechanism.
- Property-test binaries were compiled with clang++ (environment g++
  breakage, documented above); all numeric gates matched W-62's recorded
  values.

## Artifacts

- Runs: scratch/w65/runs/A3p/<model>/w1000_pf/rep<r>_c<c>.{csv,log}
  (120/120 done); driver scratch/w65/driver.py + driver.log; WORKERS=4.
- Gates/canaries: scratch/w65/gates/ (default-path new-vs-base csvs+logs,
  A2-no-auto blr pin cell); E1 probes scratch/w65/probe/.
- Analysis: scratch/w65/analyze_w65.py -> scratch/w65/w65_results.json.
- This file: results/lowrank_screened_w65.md; WORKLOG close-out entry
  appended same session.
